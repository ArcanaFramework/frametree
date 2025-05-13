from __future__ import annotations
import logging
import re
import typing as ty
from pathlib import Path
import shutil
from warnings import warn
import attrs
import attrs.filters
from attrs.converters import default_if_none
from typing_extensions import Self
from pydra.compose import workflow
from pydra.utils.hash import hash_single, bytes_repr_mapping_contents
from fileformats.text import Plain as PlainText
from frametree.core.exceptions import (
    FrameTreeDataMatchError,
    FrameTreeLicenseNotFoundError,
    FrameTreeNameError,
    FrameTreeUsageError,
    FrameTreeWrongAxesError,
)
from frametree.core.licence import License
from ..column import DataColumn, SinkColumn, SourceColumn
from ..row import DataRow
from .. import store as datastore
from ..tree import DataTree
from ..axes import Axes
from .metadata import Metadata, metadata_converter


if ty.TYPE_CHECKING:  # pragma: no cover
    from frametree.core.entry import DataEntry
    from frametree.core.pipeline import Pipeline, PipelineField

logger = logging.getLogger("frametree")


def hierarchy_converter(hierarchy: ty.List[ty.Union[str, Axes]]) -> ty.List[str]:
    return [str(f) for f in hierarchy]


@attrs.define
class FrameSet:
    """
    A representation of a "dataset", the complete collection of data
    (file-sets and fields) to be used in an analysis.

    Parameters
    ----------
    id : str
        The dataset id/path that uniquely identifies the dataset within the
        store it is stored (e.g. FS directory path or project ID)
    store : Repository
        The store the dataset is stored into. Can be the local file
        system by providing a MockRemote repo.
    axes: Axes
        The space of the dataset. See https://frametree.readthedocs.io/en/latest/data_model.html#spaces)
        for a description
    id_patterns : dict[str, str]
        Patterns for inferring IDs of rows not explicitly present in the hierarchy of
        the data tree. See ``Store.infer_ids()`` for syntax
    hierarchy : list[str]
        The categorical variables that are explicitly present in the data tree.
        For example, if a MockRemote dataset (i.e. directory) has
        two layer hierarchy of sub-directories, the first layer of
        sub-directories labelled by unique subject ID, and the second directory
        layer labelled by study time-point then the hierarchy would be

            ['subject', 'visit']

        Alternatively, in some stores (e.g. XNAT) the second layer in the
        hierarchy may be named with session ID that is unique across the project,
        in which case the layer dimensions would instead be

            ['subject', 'session']

        In such cases, if there are multiple visits, the visit ID of the
        session will need to be extracted using the `id_patterns` argument.

        Alternatively, the hierarchy could be organised such that the tree
        first splits on longitudinal time-points, then a second directory layer
        labelled by member ID, with the final layer containing sessions of
        matched members labelled by their groups (e.g. test & control):

            ['visit', 'member', 'group']

        Note that the combination of layers in the hierarchy must span the
        space defined in the Axes enum, i.e. the "bitwise or" of the
        layer values of the hierarchy must be 1 across all bits
        (e.g. 'session': 0b111).
    metadata : dict or Metadata
        Generic metadata associated with the dataset, e.g. authors, funding sources, etc...
    include : list[tuple[Axes, str or ty.List[str]]]
        The IDs to be included in the dataset per row_frequency. E.g. can be
        used to limit the subject IDs in a project to the sub-set that passed
        QC. If a row_frequency is omitted or its value is None, then all available
        will be used
    exclude : list[tuple[Axes, str or ty.List[str]]]
        The IDs to be excluded in the dataset per row_frequency. E.g. can be
        used to exclude specific subjects that failed QC. If a row_frequency is
        omitted or its value is None, then all available will be used
    name : str
        The name of the dataset as saved in the store under
    columns : list[tuple[str, SourceColumn or SinkColumn]
        The sources and sinks to be initially added to the dataset (columns are
        explicitly added when workflows are applied to the dataset).
    pipelines : dict[str, pydra.Workflow]
        Pipelines that have been applied to the dataset to generate sink
    access_args: ty.Dict[str, Any]
        Repository specific args used to control the way the dataset is accessed
    """

    LICENSES_PATH = (
        "LICENSES"  # The resource that project-specifc licenses are expected
    )

    id: str = attrs.field(converter=str, metadata={"asdict": False})
    store: datastore.Store = attrs.field()
    axes: ty.Type[Axes] = attrs.field()
    id_patterns: ty.Dict[str, str] = attrs.field(
        factory=dict, converter=default_if_none(factory=dict)
    )
    hierarchy: ty.List[str] = attrs.field(converter=hierarchy_converter)
    metadata: Metadata = attrs.field(
        factory=Metadata,
        converter=metadata_converter,
        repr=False,
    )
    include: ty.Dict[str, ty.Union[ty.List[str], str]] = attrs.field(
        factory=dict, converter=default_if_none(factory=dict), repr=False
    )
    exclude: ty.Dict[str, ty.Union[ty.List[str], str]] = attrs.field(
        factory=dict, converter=default_if_none(factory=dict), repr=False
    )
    name: str = attrs.field(default="")
    columns: ty.Dict[str, DataColumn] = attrs.field(
        factory=dict, converter=default_if_none(factory=dict), repr=False
    )
    pipelines: ty.Dict[str, Pipeline] = attrs.field(
        factory=dict, converter=default_if_none(factory=dict), repr=False
    )
    tree: DataTree = attrs.field(factory=DataTree, init=False, repr=False, eq=False)

    def __attrs_post_init__(self) -> None:
        self.tree.frameset = self
        # Set reference to pipeline in columns and pipelines
        for column in self.columns.values():
            column.frameset = self
        for pipeline in self.pipelines.values():
            pipeline.frameset = self

    @store.default
    def store_default(self) -> datastore.Store:
        from frametree.common import FileSystem

        return FileSystem()

    @axes.default
    def axes_default(self) -> ty.Type[Axes]:
        try:
            return self.store.DEFAULT_AXES  # type: ignore[attr-defined, no-any-return]
        except AttributeError:
            raise TypeError(
                f"FrameSets in {type(self.store)} need to explicitly set their axes"
            )

    @hierarchy.default
    def hierarchy_default(self) -> ty.List[str]:
        try:
            return self.store.DEFAULT_HIERARCHY  # type: ignore[attr-defined, no-any-return]
        except AttributeError:
            raise TypeError(
                f"FrameSets in {type(self.store)} need to explicitly set their hierarchy"
            )

    @name.validator
    def name_validator(self, _: ty.Any, name: str) -> None:
        if name and not name.isidentifier():
            raise FrameTreeUsageError(
                f"Name provided to dataset, '{name}' should be a valid Python identifier, "
                "i.e. contain only numbers, letters and underscores and not start with a "
                "number"
            )
        if name == self.store.EMPTY_DATASET_NAME:
            raise FrameTreeUsageError(
                f"'{self.store.EMPTY_DATASET_NAME}' is a reserved name for datasets as it is used to "
                "in place of the empty dataset name in situations where '' can't be used"
            )

    @columns.validator
    def columns_validator(self, _: ty.Any, columns: ty.Dict[str, DataColumn]) -> None:
        wrong_freq = [
            m for m in columns.values() if not isinstance(m.row_frequency, self.axes)
        ]
        if wrong_freq:
            raise FrameTreeUsageError(
                f"Data hierarchy of {wrong_freq} column specs do(es) not match "
                f"that of dataset {self.axes}"
            )

    @include.validator
    def include_validator(
        self, _: ty.Any, include: ty.Dict[str, ty.Union[str, ty.List[str]]]
    ) -> None:
        valid = set(str(f) for f in self.axes)
        freqs = set(include)
        unrecognised = freqs - valid
        if unrecognised:
            raise FrameTreeUsageError(
                f"Unrecognised frequencies in 'include' dictionary provided to {self}: "
                + ", ".join(unrecognised)
            )
        self._validate_criteria(include, "inclusion")

    @exclude.validator
    def exclude_validator(
        self, _: ty.Any, exclude: ty.Dict[str, ty.Union[str, ty.List[str]]]
    ) -> None:
        valid = set(self.hierarchy)
        freqs = set(exclude)
        unrecognised = freqs - valid
        if unrecognised:
            raise FrameTreeUsageError(
                f"Unrecognised frequencies in 'exclude' dictionary provided to {self}, "
                "only frequencies present in the dataset hierarchy are allowed: "
                + ", ".join(unrecognised)
            )
        self._validate_criteria(exclude, "exclusion")

    def _validate_criteria(
        self,
        criteria: ty.Dict[str, ty.Union[str, ty.List[str]]],
        type_: ty.Type[ty.Any],
    ) -> None:
        for freq, criterion in criteria.items():
            try:
                re.compile(criterion)
            except Exception:
                if not isinstance(criterion, list) or any(
                    not isinstance(x, str) for x in criterion
                ):
                    raise FrameTreeUsageError(
                        f"Unrecognised {type_} criterion for '{freq}' provided to {self}, "
                        f"{criterion}, should either be a list of ID strings or a valid "
                        "regular expression"
                    )

    @hierarchy.validator
    def hierarchy_validator(self, _: ty.Any, hierarchy: ty.List[str]) -> None:
        not_valid = [f for f in hierarchy if str(f) not in self.axes.__members__]
        if not_valid:
            raise FrameTreeWrongAxesError(
                f"hierarchy items {not_valid} are not part of the {self.axes} data space"
            )
        # Check that all data frequencies are "covered" by the hierarchy and
        # each subsequent
        covered = self.axes(0)
        for i, layer_str in enumerate(hierarchy):
            layer = self.axes[str(layer_str)]
            diff = (layer ^ covered) & layer
            if not diff:
                raise FrameTreeUsageError(
                    f"{layer} does not add any additional basis layers to "
                    f"previous layers {hierarchy[i:]}"
                )
            covered |= layer
        if covered != max(self.axes):
            raise FrameTreeUsageError(
                "The data hierarchy ['"
                + "', '".join(hierarchy)
                + "'] does not cover the following basis frequencies ['"
                + "', '".join(str(m) for m in (covered ^ max(self.axes)).span())
                + f"'] the '{self.axes.__module__}.{self.axes.__name__}' data space"
            )
        # if missing_axes:
        #     raise FrameTreeConstructionError(
        #         "Leaf node at %s is missing explicit IDs for the following axes, %s"
        #         ", they will be set to None, noting that an error will be raised if there "
        #         " multiple nodes for this session. In that case, set 'id-patterns' on the "
        #         "dataset to extract the missing axis IDs from composite IDs or row "
        #         "metadata",
        #         tree_path,
        #         missing_axes,
        #     )
        #     for m in missing_axes:
        #         ids[m] = None

    @id_patterns.validator
    def id_patterns_validator(self, _: ty.Any, id_patterns: ty.List[str]) -> None:
        non_valid_keys = [f for f in id_patterns if f not in self.axes.__members__]
        if non_valid_keys:
            raise FrameTreeWrongAxesError(
                f"Keys for the id_patterns dictionary {non_valid_keys} are not part "
                f"of the {self.axes} data space"
            )
        for key, expr in id_patterns.items():
            groups = list(re.compile(expr).groupindex)
            non_valid_groups = [f for f in groups if f not in self.axes.__members__]
            if non_valid_groups:
                raise FrameTreeWrongAxesError(
                    f"Groups in the {key} id_patterns expression {non_valid_groups} "
                    f"are not part of the {self.axes} data space"
                )

    def save(self, name: str | None = None) -> None:
        """Save the frameset to the store

        Parameters
        ----------
        name : str, optional
            The name of the dataset to save in the store. If not provided
            the name of the dataset is used.
        """
        if name is None:
            name = self.name if self.name else ""
        self.store.save_frameset(self, name=name)

    @classmethod
    def load(
        cls,
        id: str,
        store: ty.Optional[datastore.Store] = None,
        name: ty.Optional[str] = "",
        default_if_missing: bool = False,
        **kwargs: ty.Any,
    ) -> "FrameSet":
        """Loads a dataset from an store/ID/name string, as used in the CLI

        Parameters
        ----------
        id: str
            either the ID of a dataset if `store` keyword arg is provided or a
            "dataset ID string" in the format <store-nickname>//<dataset-id>[@<dataset-name>]
        store: Store, optional
            the store to load the dataset. If not provided the provided ID
            is interpreted as an ID string
        name: str, optional
            the name of the dataset within the project/directory
            (e.g. 'test', 'training'). Used to specify a subset of data rows
            to work with, within a greater project
        default_if_missing: bool, optional
            If True, then a new dataset is created if the dataset is not found
            in the store
        **kwargs
            keyword arguments parsed to the data store load

        Returns
        -------
        FrameSet
            the loaded dataset"""
        if store is None:
            store_name, id, parsed_name = cls.parse_id_str(id)
            store = datastore.Store.load(store_name, **kwargs)
            if not name and parsed_name:
                name = parsed_name
        try:
            return store.load_frameset(id, name=name)
        except KeyError:
            if default_if_missing:
                return cls(id, store, **kwargs)
            raise

    def reload(self) -> Self:
        """Reload the frameset from the store

        Returns
        -------
        FrameSet
            The reloaded frame-set
        """
        return self.store.load_frameset(self.id, name=self.name)

    @property
    def root_freq(self) -> Axes:
        return self.axes(0)

    @property
    def root_dir(self) -> Path:
        return Path(self.id)

    @property
    def leaf_freq(self) -> Axes:
        return max(self.axes)  # type: ignore[no-any-return]

    @property
    def prov(self) -> ty.Dict[str, ty.Any]:
        return {
            "id": self.id,
            "store": self.store.prov,
            "ids": {str(freq): tuple(ids) for freq, ids in self.rows.items()},
        }

    @property
    def root(self) -> DataRow:
        """Lazily loads the data tree from the store on demand and return root

        Returns
        -------
        DataRow
            The root row of the data tree
        """
        # Build the tree cache and return the tree root. Note that if there is a
        # "with <this-dataset>.tree" statement further up the call stack then the
        # cache won't be broken down until the highest cache statement exits
        with self.tree:
            return self.tree.root

    @property
    def address(self) -> str:
        if self.store.name is None:
            raise Exception(
                f"Must save store {self.store} first before accessing locator for "
                f"{self}"
            )
        address = f"{self.store.name}//{self.id}"
        if self.name:
            address += f"@{self.name}"
        return address

    @property
    def locator(self) -> str:
        warn("'FrameSet.locator' is deprecated use, 'address' instead'")
        return self.address

    def add_source(
        self,
        name: str,
        datatype: type,
        path: ty.Optional[str] = None,
        row_frequency: ty.Optional[str] = None,
        overwrite: bool = False,
        **kwargs: ty.Any,
    ) -> SourceColumn:
        """Specify a data source in the dataset, which can then be referenced
        when connecting workflow inputs.

        Parameters
        ----------
        name : str
            The name used to reference the dataset "column" for the
            source
        datatype : type
            The file-format (for file-sets) or datatype (for fields)
            that the source will be stored in within the dataset
        path : str, default `name`
            The location of the source within the dataset
        row_frequency : Axes, default self.leaf_freq
            The row_frequency of the source within the dataset
        overwrite : bool
            Whether to overwrite existing columns
        **kwargs : ty.Dict[str, Any]
            Additional kwargs to pass to SourceColumn.__init__
        """
        if path is None:
            path = name
        source = SourceColumn(
            name=name,
            datatype=datatype,
            path=path,
            row_frequency=self.parse_frequency(row_frequency),
            frameset=self,
            **kwargs,
        )
        self._add_column(name, source, overwrite)
        return source

    def add_sink(
        self,
        name: str,
        datatype: type,
        row_frequency: ty.Optional[str] = None,
        overwrite: bool = False,
        **kwargs: ty.Any,
    ) -> SinkColumn:
        """Specify a data source in the dataset, which can then be referenced
        when connecting workflow inputs.

        Parameters
        ----------
        name : str
            The name used to reference the dataset "column" for the
            sink
        datatype : type
            The file-format (for file-sets) or datatype (for fields)
            that the sink will be stored in within the dataset
        path : str, optional
            Specify a particular for the sink within the dataset, defaults to the column
            name within the dataset derivatives directory of the store
        row_frequency : str, optional
            The row_frequency of the sink within the dataset, by default the leaf
            frequency of the data tree
        overwrite : bool
            Whether to overwrite an existing sink
        """
        sink = SinkColumn(
            name=name,
            datatype=datatype,
            row_frequency=self.parse_frequency(row_frequency),
            frameset=self,
            **kwargs,
        )
        self._add_column(name, sink, overwrite)
        return sink

    def _add_column(self, name: str, spec: DataColumn, overwrite: bool) -> None:
        if name in self.columns:
            if overwrite:
                logger.info(
                    f"Overwriting {self.columns[name]} with {spec} in " f"{self}"
                )
            else:
                raise FrameTreeNameError(
                    name,
                    f"Name clash attempting to add {spec} to {self} "
                    f"with {self.columns[name]}. Use 'overwrite' option "
                    "if this is desired",
                )
        self.columns[name] = spec

    def row(
        self,
        frequency: ty.Union[Axes, str, None] = None,
        id: ty.Union[str, ty.Tuple[str, ...]] = attrs.NOTHING,
        **id_kwargs: ty.Any,
    ) -> DataRow:
        """Returns the row associated with the given frequency and ids dict

        Parameters
        ----------
        frequency : Axes or str
            The frequency of the row
        id : str or Tuple[str], optional
            The ID of the row to
        **id_kwargs : Dict[str, str]
            Alternatively to providing `id`, ID corresponding to the row to
            return passed as kwargs

        Returns
        -------
        DataRow
            The selected data row

        Raises
        ------
        FrameTreeUsageError
            Raised when attempting to use IDs with the frequency associated
            with the root row
        FrameTreeNameError
            If there is no row corresponding to the given ids
        """
        with self.tree:
            # Parse str to frequency enums
            if not frequency:
                if id not in (None, attrs.NOTHING):
                    raise FrameTreeUsageError(f"Root rows don't have any IDs ({id})")
                return self.root
            frequency = self.parse_frequency(frequency)
            if id is not attrs.NOTHING:
                if id_kwargs:
                    raise FrameTreeUsageError(
                        f"ID ({id}) and id_kwargs ({id_kwargs}) cannot be both "
                        f"provided to `row` method of {self}"
                    )
                try:
                    return self.root.children[frequency][id]
                except KeyError as e:
                    if isinstance(id, tuple) and len(id) == self.axes.ndim:
                        # Expand ID tuple to see if it is an expansion of the ID axes
                        # instead of a direct label for the row
                        id_kwargs = {a: i for a, i in zip(self.axes.bases(), id)}
                    else:
                        raise FrameTreeNameError(
                            id,
                            f"{id} not present in data tree "
                            f"({list(self.row_ids(frequency))})",
                        ) from e
            elif not id_kwargs:
                raise FrameTreeUsageError(
                    f"Neither ID nor id_kwargs cannot were provided `row` method of {self}"
                )
            # Iterate through the tree to find the row (i.e. tree node) matching the
            # provided IDs
            row = self.root
            cum_freq = self.axes(0)
            for freq, id in id_kwargs.items():
                cum_freq |= freq
                try:
                    row = row.children[cum_freq][id]
                except KeyError as e:
                    raise FrameTreeNameError(
                        id, f"{id} ({freq}) not a child row of {row}"
                    ) from e
            if cum_freq != frequency:
                raise FrameTreeUsageError(
                    f"Cumulative frequency of ID kwargs {id_kwargs} ({cum_freq}) does not "
                    "match that of row"
                )
            return row

    def rows(
        self,
        frequency: ty.Optional[str] = None,
        ids: ty.Optional[ty.Collection[str]] = None,
    ) -> ty.List[DataRow]:
        """Return all the IDs in the dataset for a given frequency

        Parameters
        ----------
        frequency : Axes, optional
            The "frequency" of the rows, e.g. per-session, per-subject, defaults to
            leaf rows
        ids : Sequence[str or Tuple[str]]
            The i

        Returns
        -------
        Sequence[DataRow]
            The sequence of the data row within the dataset
        """
        if frequency is None:
            frequency = max(self.axes)  # "leaf" nodes of the data tree
        else:
            frequency = self.parse_frequency(frequency)
        with self.tree:
            if frequency == self.root_freq:
                return [self.root]
            try:
                rows = self.root.children[frequency].values()
            except KeyError:
                raise RuntimeError(
                    f"{frequency} was not present in {self}: {self.root.children}"
                )
            if ids is not None:
                rows = (n for n in rows if n.id in set(ids))
            return rows

    def row_ids(self, frequency: ty.Optional[str] = None) -> ty.List[ty.Optional[str]]:
        """Return all the IDs in the dataset for a given row_frequency

        Parameters
        ----------
        frequency : str
            The "frequency" of the rows to return the IDs for, e.g. per-session, per-subject...

        Returns
        -------
        Sequence[str]
            The IDs of the rows
        """
        if frequency is None:
            frequency = max(self.axes)  # "leaf" nodes of the data tree
        else:
            frequency = self.parse_frequency(frequency)
        if frequency == self.root_freq:
            return [None]
        with self.tree:
            try:
                return list(self.root.children[frequency].keys())
            except KeyError:
                return []

    def __getitem__(self, name: str) -> DataColumn:
        """Return all data items across the dataset for a given source or sink

        Parameters
        ----------
        name : str
            Name of the column to return

        Returns
        -------
        DataColumn
            the column object
        """
        return self.columns[name]

    def apply(
        self,
        name: str,
        task: workflow.Task,
        inputs: ty.List[
            ty.Union[
                "PipelineField",
                ty.Tuple[str, str, type],
                ty.Tuple[str, str],
            ]
        ],
        outputs: ty.List[
            ty.Union[
                "PipelineField",
                ty.Tuple[str, str, type],
                ty.Tuple[str, str],
            ]
        ],
        row_frequency: ty.Union[Axes, str, None] = None,
        overwrite: bool = False,
        converter_args: ty.Optional[ty.Dict[str, ty.Any]] = None,
    ) -> "Pipeline":
        """Connect a Pydra workflow as a pipeline of the dataset

        Parameters
        ----------
        name : str
            name of the pipeline
        workflow : pydra.Workflow
            pydra workflow to connect to the dataset as a pipeline
        inputs : list[frametree.core.pipeline.Input or tuple[str, str, type] or tuple[str, str]]
            List of inputs to the pipeline (see `frametree.core.pipeline.Pipeline.PipelineInput`)
        outputs : list[frametree.core.pipeline.Output or tuple[str, str, type] or tuple[str, str]]
            List of outputs of the pipeline (see `frametree.core.pipeline.Pipeline.PipelineOutput`)
        row_frequency : str, optional
            the frequency of the data rows the pipeline will be executed over, i.e.
            will it be run once per-session, per-subject or per whole dataset,
            by default the highest row frequency (e.g. per-session for Clinical)
        overwrite : bool, optional
            overwrite connections to previously connected sinks, by default False
        converter_args : dict[str, dict]
            keyword arguments passed on to the converter to control how the
            conversion is performed.

        Returns
        -------
        Pipeline
            the pipeline added to the dataset

        Raises
        ------
        FrameTreeUsageError
            if overwrite is false and
        """
        from frametree.core.pipeline import Pipeline

        row_frequency = self.parse_frequency(row_frequency)

        # def parsed_conns(lst, conn_type):
        #     parsed = []
        #     for spec in lst:
        #         if isinstance(spec, conn_type):
        #             parsed.append(spec)
        #         elif len(spec) == 3:
        #             parsed.append(conn_type(*spec))
        #         else:
        #             col_name, field = spec
        #             parsed.append(conn_type(col_name, field, self[col_name].datatype))
        #     return parsed

        pipeline = Pipeline(
            name=name,
            frameset=self,
            row_frequency=row_frequency,
            task=task,
            inputs=inputs,
            outputs=outputs,
            converter_args=converter_args,
        )
        for outpt in pipeline.outputs:
            sink = self[outpt.name]
            if sink.pipeline_name is not None:
                if overwrite:
                    logger.info(
                        f"Overwriting pipeline of sink '{outpt.name}' "
                        f"{sink.pipeline_name} with {name}"
                    )
                else:
                    raise FrameTreeUsageError(
                        f"Attempting to overwrite pipeline of '{outpt.name}' "
                        f"sink ({sink.pipeline_name}) with {name}. Use "
                        f"'overwrite' option if this is desired"
                    )
            sink.pipeline_name = pipeline.name
        self.pipelines[name] = pipeline

        return pipeline

    def derive(
        self,
        *sink_names: str,
        ids: ty.Optional[ty.Iterable[str]] = None,
        cache_dir: Path = None,
        **kwargs: ty.Any,
    ) -> None:
        """Generate derivatives from the workflows

        Parameters
        ----------
        *sink_names : Iterable[str]
            Names of the columns corresponding to the items to derive
        ids : Iterable[str]
            The IDs of the data rows in each column to derive
        cache_dir

        Returns
        -------
        Sequence[List[DataType]]
            The derived columns
        """
        from frametree.core.pipeline import Pipeline

        sinks = [self[s] for s in set(sink_names)]
        for pipeline, _ in Pipeline.stack(*sinks):
            # Execute pipelines in stack
            # FIXME: Should combine the pipelines into a single workflow and
            # dilate the IDs that need to be run when summarising over different
            # data axes
            with self.tree:
                pipeline(ids=ids)(cache_root=cache_dir, **kwargs)

    def parse_frequency(self, freq: ty.Union[Axes, str, None]) -> Axes:
        """Parses the data row_frequency, converting from string if necessary and
        checks it matches the dimensions of the dataset"""
        if freq is None:
            return max(self.axes)
        try:
            if isinstance(freq, str):
                freq = self.axes[freq]
            elif not isinstance(freq, self.axes):
                raise KeyError
        except KeyError as e:
            raise FrameTreeWrongAxesError(
                f"{freq} is not a valid dimension for {self} " f"({self.axes})"
            ) from e
        return freq

    @classmethod
    def _sink_path(cls, workflow_name: str, sink_name: str) -> str:
        return f"{workflow_name}/{sink_name}"

    @classmethod
    def parse_id_str(cls, id: str) -> ty.Tuple[str, str, str]:
        parts = id.split("//")
        if len(parts) == 1:  # No store definition, default to the `FileSystem` store
            store_name = "file_system"
        else:
            store_name, id = parts
        parts = id.split("@")
        if len(parts) == 1:
            name = ""
        else:
            id, name = parts
        return store_name, id, name

    def download_licenses(self, licenses: ty.List[License]) -> None:
        """Install licenses from project-specific location in data store and
        install them at the destination location

        Parameters
        ----------
        licenses : list[License]
            the list of licenses stored in the dataset or in a site-wide location that
            need to be downloaded to the local file-system before a pipeline is run

        Raises
        ------
        FrameTreeLicenseNotFoundError
            raised if the license of the given name isn't present in the project-specific
            location to retrieve
        """

        site_licenses_dataset = self.store.site_licenses_dataset()

        for lic in licenses:

            missing = False
            try:
                license_file = self.get_license_file(lic.name)
            except FrameTreeDataMatchError:
                if site_licenses_dataset is not None:
                    try:
                        license_file = self.get_license_file(
                            lic.name, dataset=site_licenses_dataset
                        )
                    except FrameTreeDataMatchError:
                        missing = True
                else:
                    missing = True
            if missing:
                msg = (
                    f"Did not find a license corresponding to '{lic.name}' at "
                    f"{License.column_path(lic.name)} in {self}"
                )
                if site_licenses_dataset:
                    msg += f" or {site_licenses_dataset}"
                raise FrameTreeLicenseNotFoundError(
                    lic.name,
                    msg,
                )
            shutil.copyfile(license_file, lic.destination)

    def install_license(self, name: str, source_file: PlainText) -> None:
        """Store project-specific license in dataset

        Parameters
        ----------
        name : str
            name of the license to install
        source_file : PlainText
            the license file to install
        """

        try:
            entry = self._get_license_entry(name)
        except FrameTreeDataMatchError:
            entry = self.store.create_entry(
                License.column_path(name), PlainText, self.root
            )
        self.store.put(PlainText(source_file), entry)

    def _get_license_entry(self, name: str, dataset: "FrameSet" = None) -> DataEntry:

        if dataset is None:
            dataset = self
        column = SinkColumn(
            name=f"{name}_license",
            datatype=PlainText,
            row_frequency=self.root_freq,
            frameset=dataset,
            path=License.column_path(name),
        )
        return column.match_entry(dataset.root)

    def get_license_file(
        self, name: str, dataset: ty.Optional["FrameSet"] = None
    ) -> PlainText:
        return PlainText(self._get_license_entry(name, dataset).item)

    def infer_ids(
        self, ids: ty.Dict[str, str], metadata: ty.Dict[str, ty.Dict[str, str]]
    ) -> ty.Dict[str, str]:
        return self.store.infer_ids(
            ids=ids, id_patterns=self.id_patterns, metadata=metadata
        )

    def __bytes_repr__(
        self, cache: ty.Dict[str, ty.Any]
    ) -> ty.Generator[bytes, None, None]:
        """For Pydra input hashing"""
        yield f"{type(self).__module__}.{type(self).__name__}(".encode()
        yield self.id.encode()
        yield bytes(hash_single(self.store, cache))
        yield bytes(hash_single(self.axes, cache))
        yield bytes(hash_single(self.include, cache))
        yield bytes(hash_single(self.exclude, cache))
        yield self.name.encode()
        yield from bytes_repr_mapping_contents(self.columns, cache)


@attrs.define
class SplitDataset:
    """A dataset created by combining multiple datasets into a conglomerate

    Parameters
    ----------
    """

    source_dataset: FrameSet = attrs.field()
    sink_dataset: FrameSet = attrs.field()


__all__ = ["FrameSet", "SplitDataset"]

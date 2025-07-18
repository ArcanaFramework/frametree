from __future__ import annotations
from abc import abstractmethod, ABCMeta
import re
import typing as ty
import logging
import attrs
import inspect
from operator import attrgetter
from attrs.converters import optional
from fileformats.core import DataType, Field, from_mime
from fileformats.core.exceptions import FormatMismatchError
from pydra.utils.hash import hash_single
from pydra.utils.typing import is_fileset_or_union
from frametree.core.exceptions import FrameTreeDataMatchError
from .salience import ColumnSalience
from .quality import DataQuality
from .axes import Axes
from .cell import DataCell
from .entry import DataEntry

if ty.TYPE_CHECKING:  # pragma: no cover
    from .row import DataRow
    from .frameset.base import FrameSet


logger = logging.getLogger("frametree")


def datatype_converter(datatype: ty.Union[type, str]) -> ty.Type[DataType]:
    """Convert a datatype to a DataType subclass if it is not already one

    Parameters
    ----------
    datatype : type or str
        The type, or MIME-like string, to convert into a fileformat.core.DataType

    Returns
    -------
    ty.Type[DataType]
        The converted datatype

    Raises
    ------
    TypeError
        If the datatype is not a subclass of DataType or a primitive type"""
    if ty.get_origin(datatype) is ty.Union:
        return ty.Union.__getitem__(
            tuple(datatype_converter(a) for a in ty.get_args(datatype))
        )
    if inspect.isclass(datatype) and issubclass(datatype, DataType):
        return datatype
    elif isinstance(datatype, str) and "/" in datatype:
        return from_mime(datatype)
    else:
        try:
            return Field.from_primitive(datatype)
        except TypeError:
            raise TypeError(
                f"Datatype ({datatype}) must be a subclass of {DataType}, or "
                "a primitive type of a Field datatype (i.e. int, str, float, list, etc...)"
            )


@attrs.define(kw_only=True)
class DataColumn(metaclass=ABCMeta):

    name: str
    datatype: ty.Type[DataType] = attrs.field(converter=datatype_converter)
    row_frequency: Axes = attrs.field(validator=attrs.validators.instance_of(Axes))
    path: ty.Optional[str] = None
    frameset: FrameSet = attrs.field(
        default=None, metadata={"asdict": False}, eq=False, hash=False, repr=False
    )
    _mismatch_log: list = attrs.field(
        default=None, eq=False, hash=False, repr=False, init=False
    )

    is_sink = False

    @datatype.validator
    def datatype_validator(self, _, datatype):
        if not is_fileset_or_union(datatype) and not (
            inspect.isclass(datatype) and issubclass(datatype, DataType)
        ):
            raise TypeError(f"Datatype ({datatype}) must be a subclass of {DataType}")

    def __iter__(self) -> ty.Iterable[DataType]:
        "Iterator over all items in the column, requires none of the cells to be empty"
        return (cell.item for cell in self.cells(allow_empty=False))

    def __getitem__(self, id) -> DataType:
        # TODO: could be nice to expand this to be a slice of ids
        return self.cell(id, allow_empty=False).item

    def __len__(self) -> int:
        return len(list(self.frameset.rows(self.row_frequency)))

    def cell(self, id, allow_empty: bool = True) -> DataCell:
        return DataCell.intersection(
            self,
            self.frameset.row(id=id, frequency=self.row_frequency),
            allow_empty=allow_empty,
        )

    def cells(self, allow_empty: ty.Optional[bool] = None) -> ty.Iterable[DataCell]:
        """Return an iterator over all cells in the column.

        Parameters
        ----------
        allow_empty : bool, optional
            whether to allow cells to be empty (i.e. if they don't match to an entry
            in the corresponding dataset row). If None, then cells of sink columns can
            be empty (i.e. not derived yet) and source columns can't, by default None

        Returns
        -------
        cells : Iterable[DataCell]
            an iterator over all cells in the column
        """
        return (
            DataCell.intersection(self, row, allow_empty=allow_empty)
            for row in self.frameset.rows(self.row_frequency)
        )

    @property
    def ids(self) -> ty.List[str]:
        return [n.id for n in self.frameset.rows(self.row_frequency)]

    def match_entry(self, row: DataRow, allow_none: bool = False) -> DataEntry:
        """Matches a single entry from a data row against the selection criteria
        defined in the column.

        Parameters
        ----------
        row: DataRow
            the row to match the item from
        allow_none: bool
            whether to return None if there are not matches

        Returns
        -------
        DataType or None
            the data item that matches the criteria/path

        Raises
        ------
        FrameTreeDataMatchError
            if none or multiple items match the criteria/path of the column
            within the row
        """
        matches = row.entries
        self._mismatch_log = []
        for method in self.criteria():
            filtered = [m for m in matches if method(m)]
            if not filtered:
                if allow_none:
                    return None
                else:
                    msg = (
                        "Did not find any entries "
                        + method.__doc__.format(self=self)
                        + self._error_msg(row, matches)
                        + "\n\nDetails\n"
                        + "-------\n"
                        + "\n".join(
                            frmt.format(*ags) for frmt, ags in self._mismatch_log
                        )
                    )
                    raise FrameTreeDataMatchError(msg)
            matches = filtered
        self._mismatch_log = None
        return self.select_entry_from_matches(row, matches)

    @abstractmethod
    def criteria(self) -> ty.List[ty.Callable]:
        """returns all methods used to filter out potential matches"""

    @abstractmethod
    def format_criteria(self) -> str:
        """Formats the criteria used to match entries for use in informative error messages"""

    def matches_path(self, entry: DataEntry) -> bool:
        "that matched the path '{self.path}'"
        path, dataset_name = DataEntry.split_dataset_name_from_path(self.path)
        path_parts = self.path_split_re.split(path)
        entry_parts = self.path_split_re.split(entry.base_path)[: len(path_parts)]
        if entry_parts == path_parts:
            if dataset_name == entry.dataset_name or dataset_name == "*":
                return True
            else:
                return self._log_mismatch(
                    entry,
                    "dataset_name '{}' does not match requested '{}'",
                    entry.dataset_name,
                    dataset_name,
                )
        else:
            return self._log_mismatch(
                entry,
                "path sections {} do not match {}",
                entry_parts,
                path_parts,
            )

    def matches_datatype(self, entry: DataEntry) -> bool:
        "that matched the datatype '{self.datatype.mime_like}'"
        if self.datatype is entry.datatype:
            return True
        if not is_fileset_or_union and (
            not inspect.isclass(self.datatype)
            or not issubclass(self.datatype, entry.datatype)
        ):
            return self._log_mismatch(
                entry,
                "required datatype '{}' is not a " "sub-type of '{}'",
                self.datatype.mime_like,
                entry.datatype,
            )
        try:
            entry.get_item(self.datatype)
        except FormatMismatchError as e:
            return self._log_mismatch(entry, "datatype does not match, {}", str(e))
        else:
            return True

    def select_entry_from_matches(
        self, row: DataRow, matches: ty.List[DataEntry]
    ) -> DataEntry:
        if len(matches) > 1:
            raise FrameTreeDataMatchError(
                "Found multiple matches " + self._error_msg(row, matches)
            )
        return matches[0]

    def _error_msg(self, row: DataRow, matches: ty.List[DataEntry]) -> str:
        row_str = f"'{row.id}' {row.frequency}" if row.id is not None else "root"
        return (
            f", when attempting to match an entry to the '{self.name}' column "
            f"in the {row_str} row of {self.frameset}\n\n  Found:"
            + self._format_matches(matches)
            + self.format_criteria()
        )

    def _format_matches(self, matches: ty.List[DataEntry]) -> str:
        out_str = ""
        for match in sorted(matches, key=attrgetter("path")):
            out_str += "\n    "
            if match.order:
                out_str += match.order + ": "
            out_str += match.path
            out_str += f" ({match.quality})"
        return out_str

    def _log_mismatch(self, entry, format_str, *args):
        self._mismatch_log.append(("Entry {}: " + format_str, (entry.path,) + args))
        return False

    # Split a path into sections delimited by '/' or '.'
    path_split_re = re.compile(r"/|\.|@")

    def __bytes_repr__(self, cache):
        """For Pydra input hashing"""
        yield f"{type(self).__module__}.{type(self).__name__}:".encode()
        yield self.name.encode()
        yield bytes(hash_single(self.datatype, cache))
        yield bytes(hash_single(self.row_frequency, cache))
        yield bytes(hash_single(self.path, cache))


@attrs.define(kw_only=True)
class SourceColumn(DataColumn):
    """
    Specifies the criteria by which an item is selected from a data row to
    be a data source.

    Parameters
    ----------
    name: str
        the name of the column
    datatype : type
        the data type of items in the column
    row_frequency : Axes
        the frequency of the "rows" (data nodes) within the dataset tree, e.g. for the
        ``Clinical`` data spce the row frequency can be per 'session', 'subject',
        'visit', 'group', 'dataset', et...
    dataset: FrameSet
        the dataset the column belongs to
    path : str
        A regex name_path to match the fileset names with. Must match
        one and only one fileset per <row_frequency>. If None, the name
        is used instead.
    quality_threshold : DataQuality
        The acceptable quality (or above) that should be considered. Data items
        will be considered missing
    order : int | None
        To be used to distinguish multiple filesets that match the
        name_path in the same session. The order of the fileset within the
        session (0-indexed). Based on the scan ID but is more robust to small
        changes to the IDs within the session if for example there are
        two scans of the same type taken before and after a task.
    required_metadata : dict[str, ty.Any]
        Required metadata, which can be used to distinguish multiple items that match all
        other criteria. The provided dictionary contains metadata values that must match
        the stored required_metadata exactly.
    is_regex : bool
        Flags whether the name_path is a regular expression or not
    """

    quality_threshold: DataQuality = attrs.field(
        default=None, converter=optional(lambda q: DataQuality[str(q)])
    )
    order: int = attrs.field(
        default=None, converter=lambda x: int(x) if x is not None else None
    )
    required_metadata: ty.Dict[str, ty.Any] = attrs.field(default=None)
    is_regex: bool = attrs.field(
        default=False,
        converter=lambda x: x.lower() == "true" if isinstance(x, str) else x,
    )

    def criteria(self) -> ty.List[ty.Callable]:
        criteria = []
        if self.path is not None:
            if self.is_regex:
                criteria.append(self.matches_path_regex)
            else:
                criteria.append(self.matches_path)
        if self.quality_threshold is not None:
            criteria.append(self.matches_quality)
        if self.required_metadata is not None:
            criteria.append(self.matches_metadata)
        criteria.append(self.matches_datatype)
        return criteria

    def format_criteria(self) -> str:
        msg = "\n\n  Criteria: "
        if self.path:
            msg += f"\n    path='{self.path}'"
            if self.is_regex:
                msg += " (regular-expression)" if self.is_regex else ""
        if self.quality_threshold:
            msg += f"\n    quality_threshold='{self.quality_threshold}'"
        if self.required_metadata:
            msg += f"\n    required_metadata={self.required_metadata}"
        msg += f"\n    datatype='{self.datatype.mime_like}'"
        if self.order:
            msg += f"\n    order={self.order}"
        return msg

    def matches_path_regex(self, entry: DataEntry) -> bool:
        "that matched the path pattern '{self.path}'"
        pattern = self.path
        if not pattern.endswith("$"):
            # Allow paths to match with additional text after a '/' or a '.' but not
            # additional characters otherwise
            pattern += r"(?:(?:/|\.).*)?$"
        if re.match(pattern, entry.path):
            return True
        else:
            return self._log_mismatch(
                entry, "entry path {} doesn't match regular expression", pattern
            )

    def matches_quality(self, entry: DataEntry) -> bool:
        "with an acceptable quality '{self.quality_threshold}'"
        if entry.quality >= self.quality_threshold:
            return True
        else:
            return self._log_mismatch(
                entry, "quality is below threshold {}", self.quality_threshold
            )

    def matches_metadata(self, entry: DataEntry) -> bool:
        "with the required metadata '{self.required_metadata}'"
        entry_metadata = {k: entry.item_metadata[k] for k in self.required_metadata}
        if entry_metadata == self.required_metadata:
            return True
        else:
            return self._log_mismatch(
                entry,
                "metadata {} doesn't match required {}",
                entry_metadata,
                self.required_metadata,
            )

    def select_entry_from_matches(
        self, row: DataRow, matches: ty.List[DataEntry]
    ) -> DataEntry:
        # Select a single item from the ones that match the criteria
        if self.order is not None:
            try:
                return matches[self.order - 1]
            except IndexError as e:
                raise FrameTreeDataMatchError(
                    f"Not enough matching items in row {row.id} {row.frequency} in the "
                    f"'{self.name}' column to select one at index {self.order} "
                    "(starting from 1), found:" + self._format_matches(matches)
                ) from e
        else:
            return super().select_entry_from_matches(row, matches)

    def __bytes_repr__(self, cache):
        """For Pydra input hashing"""
        yield from super().__bytes_repr__(cache)
        yield bytes(hash_single(self.quality_threshold, cache))
        yield bytes(hash_single(self.order, cache))
        yield bytes(hash_single(self.required_metadata, cache))
        yield bytes(hash_single(self.is_regex, cache))


@attrs.define(kw_only=True)
class SinkColumn(DataColumn):
    """
    A specification for a file set within a analysis to be derived from a
    processing pipeline.

    Parameters
    ----------
    name: str
        the name of the column
    datatype : type
        the data type of items in the column
    row_frequency : Axes
        the frequency of the "rows" (data nodes) within the dataset tree, e.g. for the
        ``Clinical`` data spce the row frequency can be per 'session', 'subject',
        'visit', 'group', 'dataset', et...
    dataset: FrameSet
        the dataset the column belongs to
    path : str
        A regex name_path to match the fileset names with. Must match
        one and only one fileset per <row_frequency>. If None, the name
        is used instead.
    salience : Salience
        The salience of the specified file-set, i.e. whether it would be
        typically of interest for publication outputs or whether it is just
        a temporary file in a workflow, and stages in between
    pipeline_name : str
        The name of the workflow applied to the dataset to generates the data
        for the sink
    """

    path = attrs.field(
        validator=attrs.validators.instance_of(str)
    )  # i.e. make mandatory
    salience: ColumnSalience = attrs.field(
        default=ColumnSalience.supplementary,
        converter=lambda s: ColumnSalience[str(s)] if s is not None else None,
    )
    pipeline_name: str = attrs.field(default=None)

    is_sink = True

    @path.default
    def path_default(self):
        return f"{self.name}@{self.frameset.name}"

    def derive(self, ids: ty.List[str] = None):
        self.frameset.derive(self.name, ids=ids)

    def criteria(self):
        return [self.matches_path, self.matches_datatype]

    def format_criteria(self):
        return (
            "\n\n  Criteria: "
            f"\n    path='{self.path}' "
            f"\n    datatype='{self.datatype.mime_like}' "
        )

    def __setitem__(self, id, value: DataType):
        self.cell(id, allow_empty=True).item = value

    def __bytes_repr__(self, cache):
        """For Pydra input hashing"""
        yield from super().__bytes_repr__(cache)
        yield bytes(hash_single(self.salience, cache))
        yield bytes(hash_single(self.pipeline_name, cache))

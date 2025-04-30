import attrs
import typing as ty
from collections import OrderedDict
import logging
from copy import copy
from typing_extensions import Self
import attrs.converters
from fileformats.core import DataType
from fileformats.core.exceptions import FormatConversionError
from pydra.utils.typing import StateArray
from pydra.utils import get_fields
from pydra.compose.base import Task
from pydra.compose import workflow, python
from frametree.core.exceptions import (
    FrameTreeNameError,
    FrameTreeUsageError,
    FrameTreeDesignError,
    FrameTreePipelinesStackError,
    FrameTreeOutputNotProducedException,
    FrameTreeDataMatchError,
)
import frametree.core.frameset.base
import frametree.core.row
from frametree.core.axes import Axes
from frametree.core.utils import (
    path2varname,
    add_exc_note,
)
from frametree.core.serialize import (
    asdict,
    fromdict,
    pydra_asdict,
    pydra_fromdict,
    ClassResolver,
    ObjectListConverter,
)
from frametree.core.column import SinkColumn
from frametree.core.frameset.base import FrameSet


logger = logging.getLogger("frametree")


@attrs.define
class PipelineField:
    """Defines an input to a pipeline

    Parameters
    ----------
    name : str
        Name of the input and how it will be referred to in UI
    field : str, optional
        the name of the pydra input field to connect to, defaults to name
    datatype : type, optional
        the type of the items to be passed to the input, fileformats.generic.File by default
    """

    name: str
    field: str = attrs.field()
    datatype: type = attrs.field(
        default=None,
        converter=ClassResolver(
            DataType,
            allow_none=True,
            alternative_types=[frametree.core.row.DataRow],
        ),
    )

    @field.default
    def field_default(self) -> str:
        return self.name


logger = logging.getLogger("frametree")


@attrs.define
class Pipeline:
    """A thin wrapper around a Pydra workflow to link it to sources and sinks
    within a frameset

    Parameters
    ----------
    name : str
        the name of the pipeline, used to differentiate it from others
    row_frequency : Axes, optional
        The row_frequency of the pipeline, i.e. the row_frequency of the
        derivatvies within the frameset, e.g. per-session, per-subject, etc,
        by default None
    workflow : Workflow
        The pydra workflow that performs the actual analysis
    inputs : Sequence[ty.Union[str, ty.Tuple[str, type]]]
        List of column names (i.e. either data sources or sinks) to be
        connected to the inputs of the pipeline. If the pipelines requires
        the input to be in a datatype to the source, then it can be specified
        in a tuple (NAME, FORMAT)
    outputs : Sequence[ty.Union[str, ty.Tuple[str, type]]]
        List of sink names to be connected to the outputs of the pipeline
        If the input to be in a specific datatype, then it can be provided in
        a tuple (NAME, FORMAT)
    converter_args : dict[str, dict]
        keyword arguments passed on to the converter to control how the
        conversion is performed.
    frameset : FrameSet
        the frameset the pipeline has been applied to
    """

    name: str = attrs.field()
    row_frequency: Axes = attrs.field()
    task: Task = attrs.field()
    inputs: ty.List[PipelineField] = attrs.field(
        converter=ObjectListConverter(PipelineField)
    )
    outputs: ty.List[PipelineField] = attrs.field(
        converter=ObjectListConverter(PipelineField)
    )
    converter_args: ty.Dict[str, dict] = attrs.field(
        factory=dict, converter=attrs.converters.default_if_none(factory=dict)
    )
    frameset: frametree.core.frameset.base.FrameSet = attrs.field(
        metadata={"asdict": False}, default=None, eq=False, hash=False
    )

    def __attrs_post_init__(self) -> None:
        for field in self.inputs + self.outputs:
            if field.datatype is None:
                field.datatype = self.frameset[field.name].datatype

    @inputs.validator
    def inputs_validator(self, _: ty.Any, inputs: ty.List[PipelineField]) -> None:
        for inpt in inputs:
            if inpt.datatype is frametree.core.row.DataRow:  # special case
                continue
            if self.frameset:
                column = self.frameset[inpt.name]
                # Check that a converter can be found if required
                if (
                    inpt.datatype
                    and not issubclass(inpt.datatype, column.datatype)
                    and not issubclass(column.datatype, inpt.datatype)
                ):
                    try:
                        inpt.datatype.get_converter(column.datatype)
                    except FormatConversionError as e:
                        msg = (
                            f"required to in conversion of '{inpt.name}' input "
                            f"to '{self.name}' pipeline"
                        )
                        add_exc_note(e, msg)
                        raise
            elif inpt.datatype is None:
                raise ValueError(
                    f"Datatype must be explicitly set for {inpt.name} in unbound Pipeline"
                )
            field_names = [f.name for f in get_fields(self.task)]
            if inpt.field not in field_names:
                raise FrameTreeNameError(
                    inpt.field,
                    f"{inpt.field} is not in the input spec of '{self.name}' "
                    f"pipeline: " + "', '".join(field_names),
                )

    @outputs.validator
    def outputs_validator(self, _: ty.Any, outputs: ty.List[PipelineField]) -> None:
        for outpt in outputs:
            if self.frameset:
                column = self.frameset[outpt.name]
                if column.row_frequency != self.row_frequency:
                    raise FrameTreeUsageError(
                        f"Pipeline row_frequency ('{str(self.row_frequency)}') doesn't match "
                        f"that of '{outpt.name}' output ('{str(self.row_frequency)}')"
                    )
                # Check that a converter can be found if required
                if (
                    outpt.datatype
                    and not issubclass(outpt.datatype, column.datatype)
                    and not issubclass(column.datatype, outpt.datatype)
                ):
                    try:
                        column.datatype.get_converter(outpt.datatype)
                    except FormatConversionError as e:
                        msg = (
                            f"required to in conversion of '{outpt.name}' output "
                            f"from '{self.name}' pipeline"
                        )
                        add_exc_note(e, msg)
                        raise
            elif outpt.datatype is None:
                raise ValueError(
                    f"Datatype must be explicitly set for {outpt.name} in unbound Pipeline"
                )
            field_names = [f.name for f in get_fields(self.task.Outputs)]
            if outpt.field not in field_names:
                raise FrameTreeNameError(
                    outpt.field,
                    f"{outpt.field} is not in the output spec of '{self.name}' "
                    f"pipeline: " + "', '".join(field_names),
                )

    @property
    def input_varnames(self) -> ty.List[str]:
        return [
            i.name for i in self.inputs
        ]  # [path2varname(i.name) for i in self.inputs]

    @property
    def output_varnames(self) -> ty.List[str]:
        return [
            o.name for o in self.outputs
        ]  # [path2varname(o.name) for o in self.outputs]

    # parameterisation = self.get_parameterisation(kwargs)
    # self.wf.to_process.inputs.parameterisation = parameterisation
    # self.wf.per_node.source.inputs.parameterisation = parameterisation

    def __call__(self, ids: ty.List[str] = None) -> workflow.Task:
        """
        Create an "outer" workflow that interacts with the frameset to pull input
        data, process it and then push the derivatives back to the store.

        Parameters
        ----------
        **kwargs
            passed directly to the Pydra.Workflow init. The `ids` arg can be
            used to filter the data rows over which the pipeline is run.

        Returns
        -------
        pydra.compose.workflow.Task
            a Pydra workflow that iterates through the frameset, pulls data to the
            processing node, executes the analysis workflow on each data row,
            then uploads the outputs back to the data store

        Raises
        ------
        FrameTreeUsageError
            If the new pipeline will overwrite an existing pipeline connection
            with overwrite == False.
        """
        return PipelineWorkflow(
            task=self.task,
            ids=ids,
            frameset=self.frameset,
            row_frequency=self.row_frequency,
            inputs=self.inputs,
            outputs=self.outputs,
            converter_args=self.converter_args,
        )

    PROVENANCE_VERSION = "1.0"
    WORKFLOW_NAME = "processing"

    def asdict(
        self, required_modules: ty.Optional[ty.Set[str]] = None
    ) -> ty.Dict[str, ty.Any]:
        dct = asdict(self, omit=["task"], required_modules=required_modules)
        dct["task"] = pydra_asdict(self.task, required_modules=required_modules)
        return dct

    @classmethod
    def fromdict(cls, dct: ty.Dict[str, ty.Any], **kwargs: ty.Any) -> Self:
        return fromdict(dct, task=pydra_fromdict(dct["task"]), **kwargs)

    @classmethod
    def stack(
        cls, *sinks: ty.Union[SinkColumn, str]
    ) -> ty.List[ty.Tuple["Pipeline", ty.List[SinkColumn]]]:
        """Determines the pipelines stack, in order of execution,
        required to generate the specified sink columns.

        Parameters
        ----------
        sinks : Iterable[SinkColumn or str]
            the sink columns, or their names, that are to be generated

        Returns
        -------
        ty.List[tuple[Pipeline, ty.List[SinkColumn]]]
            stack of pipelines required to produce the specified data sinks,
            along with the sinks each stage needs to produce.

        Raises
        ------
        FrameTreeDesignError
            when there are circular references in the pipelines stack
        """

        # Stack of pipelines to process in reverse order of required execution
        stack = OrderedDict()

        def push_pipeline_on_stack(
            sink: SinkColumn, downstream: ty.Optional[ty.Tuple[Pipeline]] = None
        ) -> None:
            """
            Push a pipeline onto the stack of pipelines to be processed,
            detecting common upstream pipelines and resolving them to a single
            pipeline

            Parameters
            ----------
            sink: SinkColumn
                the sink to push its deriving pipeline for
            downstream : tuple[Pipeline]
                The pipelines directly downstream of the pipeline to be added.
                Used to detect circular dependencies
            """
            if downstream is None:
                downstream = []
            if sink.pipeline_name is None:
                raise FrameTreeDesignError(
                    f"{sink} hasn't been connected to a pipeline yet"
                )
            pipeline = sink.frameset.pipelines[sink.pipeline_name]
            if sink.name not in pipeline.output_varnames:
                raise FrameTreeOutputNotProducedException(
                    f"{pipeline.name} does not produce {sink.name}"
                )
            # Check downstream piplines for circular dependencies
            downstream_pipelines = [p for p, _ in downstream]
            if pipeline in downstream_pipelines:
                recur_index = downstream_pipelines.index(pipeline)
                raise FrameTreeDesignError(
                    f"{pipeline} cannot be a dependency of itself. Call-stack:\n"
                    + "\n".join(
                        "{} ({})".format(p, ", ".join(ro))
                        for p, ro in (
                            [[pipeline, sink.name]] + downstream[: (recur_index + 1)]
                        )
                    )
                )
            if pipeline.name in stack:
                # Pop pipeline from stack in order to add it to the end of the
                # stack and ensure it is run before all downstream pipelines
                prev_pipeline, to_produce = stack.pop(pipeline.name)
                assert pipeline is prev_pipeline
                # Combined required output to produce
                to_produce.append(sink)
            else:
                to_produce = []
            # Add the pipeline to the stack
            stack[pipeline.name] = pipeline, to_produce
            # Recursively add all the pipeline's prerequisite pipelines to the stack
            for inpt in pipeline.inputs:
                inpt_column = sink.frameset[inpt.name]
                if inpt_column.is_sink:
                    try:
                        push_pipeline_on_stack(
                            inpt_column,
                            downstream=[(pipeline, to_produce)] + downstream,
                        )
                    except FrameTreePipelinesStackError as e:
                        e.msg += (
                            "\nwhich are required as inputs to the '{}' "
                            "pipeline to produce '{}'".format(
                                pipeline.name, "', '".join(s.name for s in to_produce)
                            )
                        )
                        raise e

        # Add all pipelines
        for sink in sinks:
            push_pipeline_on_stack(sink)

        return reversed(stack.values())


def append_side_car_suffix(name: str, suffix: str) -> str:
    """Creates a new combined field name out of a basename and a side car"""
    return f"{name}__o__{suffix}"


def split_side_car_suffix(name: str) -> ty.List[str]:
    """Splits the basename from a side car sufix (as combined by `append_side_car_suffix`"""
    return name.split("__o__")


@workflow.define(outputs=["processed", "cant_process"])
def PipelineWorkflow(
    task: Task,
    frameset: FrameSet,
    row_frequency: Axes,
    inputs: ty.List[PipelineField],
    outputs: ty.List[PipelineField],
    converter_args: ty.Dict[str, dict],
    ids: ty.Optional[ty.List[str]] = None,
) -> ty.Tuple[ty.List[str], ty.List[str]]:
    """Create the outer workflow to link the analysis workflow with the
    data row iteration and store connection rows
    """

    # Generate list of rows to process checking existing outputs
    to_process = workflow.add(
        ToProcess(
            frameset=frameset,
            row_frequency=row_frequency,
            outputs=outputs,
            requested_ids=ids,
        )
    )

    per_row = workflow.add(
        PipelineRowWorkflow(
            task=task,
            frameset=frameset,
            row_frequency=row_frequency,
            inputs=inputs,
            outputs=outputs,
            converter_args=converter_args,
        ).split(row_id=to_process.row_ids)
    )

    return per_row.row_id, to_process.cant_process


@workflow.define(outputs=["row_id"])
def PipelineRowWorkflow(
    task: Task,
    frameset: frametree.core.frameset.base.FrameSet,
    row_frequency: Axes,
    row_id: str,
    inputs: ty.List[PipelineField],
    outputs: ty.List[PipelineField],
    converter_args: ty.Dict[str, dict],
):

    # Get the values from the frameset, caching remote files locally
    source = workflow.add(
        SourceItems(
            frameset=frameset,
            row_frequency=row_frequency,
            row_id=row_id,
            inputs=inputs,
        )
    )

    source_types = {}
    for inpt in inputs:
        if inpt.datatype is frametree.core.row.DataRow:
            # If the input datatype is a DataRow then the source is the whole
            # row
            source_types[inpt.name] = frametree.core.row.DataRow
            continue
        # If the row frequency of the column is not a parent of the pipeline
        # then the input will be a sequence of all the child rows
        dtype = frameset[inpt.name].datatype
        # If the row frequency of the source column is higher than the frequency
        # of the pipeline, then the related elements of the source column are
        # collected into a list and passed to the pipeline
        if inpt.datatype is not frametree.core.row.DataRow and not frameset[
            inpt.name
        ].row_frequency.is_parent(row_frequency, if_match=True):
            dtype = StateArray[dtype]
        source_types[inpt.name] = dtype

    column_names = list(source_types)

    # Dynamically access the inputs from the source dictionary
    @python.define(outputs=source_types)
    def SourceOutputs(
        sources: ty.Dict[
            str, ty.Union[frametree.core.row.DataRow, DataType, ty.List[DataType]]
        ],
        column_names: ty.List[str],
    ):
        return (
            sources[column_names[0]]
            if len(column_names) == 1
            else tuple(sources[c] for c in column_names)
        )

    source_outputs = workflow.add(
        SourceOutputs(sources=source.items, column_names=column_names)
    )

    # Set the inputs
    sourced = {i.name: getattr(source_outputs, i.name) for i in inputs}

    # Do input datatype conversions if required
    for inpt in inputs:
        if inpt.datatype == frametree.core.row.DataRow:
            continue
        stored_format = frameset[inpt.name].datatype
        if (
            inpt.datatype
            and not issubclass(inpt.datatype, stored_format)
            and not issubclass(stored_format, inpt.datatype)
        ):
            converter = inpt.datatype.get_converter(stored_format)
            logger.info(
                "Adding implicit conversion for input '%s' from %s to %s",
                inpt.name,
                stored_format.mime_like,
                inpt.datatype.mime_like,
            )
            in_file = sourced.pop(inpt.name)
            converter_task = copy(converter.task)
            for nm, val in converter_args.get(inpt.name, {}).items():
                setattr(converter_task, nm, val)
            if ty.get_origin(source_types[inpt.name]) is StateArray:
                # Iterate over all items in the sequence and convert them
                # separately
                converter_task.split(converter.in_file, **{converter.in_file: in_file})
            else:
                setattr(converter_task, converter.in_file, in_file)
            # Insert converter
            converter_outputs = workflow.add(
                converter_task, name=f"{inpt.name}_input_converter"
            )
            # Map converter output to input_interface
            sourced[inpt.name] = getattr(converter_outputs, converter.out_file)

    # Copy the task of the pipeline that actually performs the analysis/processing and
    # connections from the sourced/converted inputs
    task_copy = copy(task)

    for inpt in inputs:
        setattr(
            task_copy,
            inpt.field,
            sourced[inpt.name],
        )

    # Add the task to the workflow
    task_outputs = workflow.add(task_copy, name="task")

    # Set datatype converters where required
    to_sink = {o.name: getattr(task_outputs, o.field) for o in outputs}

    # Do output datatype conversions if required
    for outpt in outputs:
        stored_format = frameset[outpt.name].datatype
        sink_name = path2varname(outpt.name)
        if (
            outpt.datatype
            and not issubclass(outpt.datatype, stored_format)
            and not issubclass(stored_format, outpt.datatype)
        ):
            converter = stored_format.get_converter(outpt.datatype)
            logger.info(
                "Adding implicit conversion for output '%s' " "from %s to %s",
                outpt.name,
                outpt.datatype.mime_like,
                stored_format.mime_like,
            )
            # Insert converter
            task_kwargs = {converter.in_file: to_sink.pop(sink_name)}
            task_kwargs.update(converter_args.get(outpt.name, {}))
            converter_task = copy(converter.task)
            for nm, val in task_kwargs.items():
                setattr(converter_task, nm, val)
            converter_task = workflow.add(
                converter_task, name=f"{sink_name}_output_converter"
            )
            # Map converter output to workflow output
            to_sink[sink_name] = getattr(converter_task, converter.out_file)

    # Dynamically collect the outputs into a dictionary
    sink_types = {o.name: frameset[o.name].datatype for o in outputs}
    column_names = list(sink_types)

    @python.define(inputs=sink_types, outputs=["items"])
    def SinkInputs(
        column_names: ty.List[str],
        **sinks: DataType,
    ) -> ty.Dict[str, DataType]:
        return {c: sinks[c] for c in column_names}

    sink_inputs = workflow.add(SinkInputs(column_names=column_names, **to_sink))

    # Can't use a decorated function as we need to allow for dynamic
    # arguments

    sink = workflow.add(
        SinkItems(
            frameset=frameset,
            row_frequency=row_frequency,
            row_id=row_id,
            items=sink_inputs.items,
        )
    )
    # we just need to return something that can be connected to downstream nodes
    return sink.row_id


@python.define(outputs=["row_ids", "cant_process"])
def ToProcess(
    frameset: frametree.core.frameset.base.FrameSet,
    row_frequency: Axes,
    outputs: ty.List[PipelineField],
    requested_ids: ty.Union[ty.List[str], None],
) -> ty.Tuple[ty.List[str], ty.List[str]]:
    if requested_ids is None:
        requested_ids = frameset.row_ids(row_frequency)
    row_ids = []
    cant_process = []
    for row in frameset.rows(row_frequency, ids=requested_ids):
        # TODO: Should check provenance of existing rows to see if it matches
        empty = [row.cell(o.name).is_empty for o in outputs]
        if all(empty):
            row_ids.append(row.id)
        elif any(empty):
            cant_process.append(row.id)
    logger.debug(
        "Found %s ids to process, and can't process %s due to partially present outputs",
        row_ids,
        cant_process,
    )
    return row_ids, cant_process


@python.define(outputs=["items"])
def SourceItems(
    frameset: frametree.core.frameset.base.FrameSet,
    row_frequency: Axes,
    row_id: str,
    inputs: ty.List[PipelineField],
) -> ty.Dict[str, ty.Union["frametree.core.row.DataRow", DataType, ty.List[DataType]]]:
    """Selects the items from the frameset corresponding to the input
    sources and retrieves them from the store to a cache on
    the host

    Parameters
    ----------
    frameset : FrameSet
        the frameset to source the data from
    row_frequency : Axes
        the frequency of the row to source the data from
    row_id : str
        the ID of the row to source from

    Returns
    -------
    dict[str, DataType | DataRow]
        the sourced data items, or the whole row if the input
    """
    logger.debug("Sourcing %s", inputs)
    sourced: ty.Dict[str, ty.Union["frametree.core.row.DataRow", DataType]] = {}
    missing_inputs: ty.Dict[str, str] = {}
    row = frameset.row(row_frequency, row_id)
    with frameset.store.connection:
        for inpt in inputs:
            # If the required datatype is of type DataRow then provide the whole
            # row to the pipeline input
            if inpt.datatype == frametree.core.row.DataRow:
                sourced[inpt.name] = row
                continue
            try:
                sourced[inpt.name] = row[inpt.name]
            except FrameTreeDataMatchError as e:
                missing_inputs[inpt.name] = str(e)
    if missing_inputs:
        raise FrameTreeDataMatchError("\n\n" + "\n\n".join(missing_inputs.values()))
    return sourced


@python.define(outputs=["row_id"])
def SinkItems(
    frameset: FrameSet,
    row_frequency: Axes,
    row_id: str,
    items: ty.Dict[str, ty.Any],
    provenance: ty.Optional[ty.Dict[str, ty.Any]] = None,
) -> str:
    """Stores items generated by the pipeline back into the store

    Parameters
    ----------
    frameset : FrameSet
        the frameset to source the data from
    row_frequency : Axes
        the frequency of the row to source the data from
    row_id : str
        the ID of the row to source from
    provenance : dict
        provenance information to be stored alongside the generated data
    **to_sink : dict[str, DataType]
        data items to be stored in the data store

    Returns
    -------
    row_id: str
        the ID of the row that was processed
    """
    if provenance is not None:
        raise NotImplementedError("Provenance storage not implemented yet")
    logger.debug("Sinking %s", items)
    row = frameset.row(row_frequency, row_id)
    with frameset.store.connection:
        for outpt_name, output in items.items():
            row.cell(outpt_name).item = output
    return row_id


# Provenance mismatch detection methods salvaged from data.provenance

# def mismatches(self, other, include=None, exclude=None):
#     """
#     Compares information stored within provenance objects with the
#     exception of version information to see if they match. Matches are
#     constrained to the name_paths passed to the 'include' kwarg, with the
#     exception of sub-name_paths passed to the 'exclude' kwarg

#     Parameters
#     ----------
#     other : Provenance
#         The provenance object to compare against
#     include : list[ty.List[str]] | None
#         Paths in the provenance to include in the match. If None all are
#         incluced
#     exclude : list[ty.List[str]] | None
#         Paths in the provenance to exclude from the match. In None all are
#         excluded
#     """
#     if include is not None:
#         include_res = [self._gen_prov_path_regex(p) for p in include]
#     if exclude is not None:
#         exclude_res = [self._gen_prov_path_regex(p) for p in exclude]
#     diff = DeepDiff(self._prov, other._prov, ignore_order=True)
#     # Create regular expressions for the include and exclude name_paths in
#     # the datatype that deepdiff uses for nested dictionary/lists

#     def include_change(change):
#         if include is None:
#             included = True
#         else:
#             included = any(rx.match(change) for rx in include_res)
#         if included and exclude is not None:
#             included = not any(rx.match(change) for rx in exclude_res)
#         return included

#     filtered_diff = {}
#     for change_type, changes in diff.items():
#         if isinstance(changes, dict):
#             filtered = dict((k, v) for k, v in changes.items()
#                             if include_change(k))
#         else:
#             filtered = [c for c in changes if include_change(c)]
#         if filtered:
#             filtered_diff[change_type] = filtered
#     return filtered_diff

# @classmethod
# def _gen_prov_path_regex(self, file_path):
#     if isinstance(file_path, str):
#         if file_path.startswith('/'):
#             file_path = file_path[1:]
#         regex = re.compile(r"root\['{}'\].*"
#                             .format(r"'\]\['".join(file_path.split('/'))))
#     elif not isinstance(file_path, re.Pattern):
#         raise FrameTreeUsageError(
#             "Provenance in/exclude name_paths can either be name_path "
#             "strings or regexes, not '{}'".format(file_path))
#     return regex

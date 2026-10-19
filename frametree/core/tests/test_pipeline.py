import typing as ty
from pathlib import Path

import pytest
from fileformats.core.exceptions import FormatConversionError
from fileformats.extras.testing import EncodedFromTextConverter, EncodedToTextConverter
from fileformats.generic import File, UnicodeFile
from fileformats.testing import EncodedText, Foo
from fileformats.text import TextFile
from pydra.compose import python

from frametree.core.frameset.base import FrameSet
from frametree.core.pipeline import RuntimeConverterWorkflow, is_coercible
from frametree.core.store.base import Store
from frametree.file_system import FileSystem
from frametree.testing import TestAxes
from frametree.testing.blueprint import FileSetEntryBlueprint as FileBP
from frametree.testing.blueprint import TestDatasetBlueprint


@python.define(outputs=["out_file"])
def EncodedTextIdentity(in_file: EncodedText) -> EncodedText:
    assert in_file.raw_contents != "file.txt"
    return in_file


@python.define(outputs=["out_file"])
def OptionalEncodedTextIdentity(in_file: EncodedText | None) -> EncodedText | None:
    assert in_file is not None
    assert in_file.raw_contents != "file.txt"
    return in_file


@python.define(outputs=["out_file"])
def OptionalTextIdentity(in_file: TextFile | None) -> TextFile | None:
    assert in_file is not None
    assert in_file.raw_contents == "file.txt"
    return in_file


@python.define(outputs=["out_file"])
def ConcatenateEncodedText(in_files: ty.List[EncodedText]) -> TextFile:
    # Every item should have already been converted from the stored TextFile
    # format to EncodedText (i.e. shifted) by a per-item converter task before
    # reaching here, so none of them should still read as the original contents
    assert all(f.raw_contents != "file.txt" for f in in_files)
    out_file = TextFile.sample()
    out_file.write_text("\n".join(f.raw_contents for f in in_files))
    return out_file


@python.define(outputs=["out_file"])
def GenericTextOutput(in_file: TextFile) -> UnicodeFile:
    # A task with a generic output datatype, whose outputs may or may not need to be
    # converted to the datatype of the column they are stored in
    return UnicodeFile(in_file)


@python.define(outputs=["out_file"])
def UnionTextOutput(in_file: EncodedText) -> EncodedText | TextFile:
    return in_file


def test_pipeline_union_column_datatype(
    saved_dataset: FrameSet, data_store: Store, work_dir: Path
):

    bp = TestDatasetBlueprint(
        hierarchy=[
            "abcd"
        ],  # e.g. XNAT where session ID is unique in project but final layer is organised by visit
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file", datatype=TextFile, filenames=["file.txt"]),
        ],
    )
    frameset = bp.make_dataset(FileSystem(), str(work_dir / "dataset"))
    frameset.add_source(
        "file",
        EncodedText.convertible_from(),  # Union datatype
    )
    frameset.add_sink(
        "out",
        TextFile,
    )

    # Start generating the arguments for the CLI
    # Add source to loaded dataset

    frameset.apply(
        "a_pipeline",
        EncodedTextIdentity(),
        inputs={
            (
                "file",
                "in_file",
                EncodedText,
            )
        },
        outputs=[
            (
                "out",
                "out_file",
                EncodedText,
            )
        ],
    )

    pipeline = frameset.pipelines["a_pipeline"]
    wf = pipeline()

    per_row = wf.construct()["PipelineRowWorkflow"]._task.construct()
    input_converter = per_row["file_input_converter"]
    output_converter = per_row["out_output_converter"]
    assert isinstance(input_converter._task, RuntimeConverterWorkflow)
    assert isinstance(output_converter._task, EncodedToTextConverter)

    out = next(iter(frameset.derive("out", cache_dir=work_dir / "cache")[0]))
    assert out.raw_contents == "file.txt"


def test_pipeline_gathers_source_column_into_list_and_converts(
    saved_dataset: FrameSet, data_store: Store, work_dir: Path
):
    """Checks that when a pipeline's row_frequency is coarser than the
    row_frequency of one of its source columns, the matching items across all the
    descendant rows are gathered into a list (rather than the pipeline being run
    once per matching row, see `test_pipeline_union_column_datatype`), *and* that a
    format conversion is still correctly applied to each item in the gathered list
    (i.e. that the per-item, split converter task added in `PipelineRowWorkflow` is
    actually reached, not just the plain list-gathering in `SourceItems`).
    """
    num_sessions = 3
    bp = TestDatasetBlueprint(
        hierarchy=["abcd"],
        axes=TestAxes,
        dim_lengths=[1, 1, 1, num_sessions],
        entries=[
            FileBP(path="file", datatype=TextFile, filenames=["file.txt"]),
        ],
    )
    frameset = bp.make_dataset(FileSystem(), str(work_dir / "dataset"))
    # "file" only exists at its natural (leaf) row_frequency, one per session
    frameset.add_source("file", TextFile, row_frequency=TestAxes.abcd)
    frameset.add_sink("out", TextFile, row_frequency=TestAxes.__)

    frameset.apply(
        "a_pipeline",
        ConcatenateEncodedText(),
        inputs=[
            (
                "file",
                "in_files",
                EncodedText,  # requires conversion from the stored TextFile format
            )
        ],
        outputs=[
            (
                "out",
                "out_file",
                TextFile,
            )
        ],
        row_frequency=TestAxes.__,  # dataset-wide, coarser than "file"'s row_frequency
    )

    pipeline = frameset.pipelines["a_pipeline"]
    wf = pipeline()

    per_row = wf.construct()["PipelineRowWorkflow"]._task.construct()
    input_converter = per_row["file_input_converter"]
    # A fixed (non-union) converter is used since the source is a single, known
    # format, and it should have been split so it runs once per gathered item
    assert isinstance(input_converter._task, EncodedFromTextConverter)
    assert input_converter.state is not None
    assert input_converter.state.splitter == "file_input_converter.in_file"

    out = next(iter(frameset.derive("out", cache_dir=work_dir / "cache")[0]))
    shifted = "".join(chr(ord(c) + 1) for c in "file.txt")  # default shift=1
    assert out.raw_contents.split("\n") == [shifted] * num_sessions


@pytest.mark.parametrize(
    "t,u,expected",
    [
        (TextFile, TextFile, True),
        # Only if the stored type is the input type or a subclass of it. An input type
        # that is more specific than the stored type depends on what the item is
        (TextFile, File, False),
        (File, TextFile, True),
        (TextFile, EncodedText, False),
        # Parameterised generics raise a TypeError with the builtin issubclass
        (list[TextFile], list[TextFile], True),
        (list[TextFile], list[File], False),
        (list[File], ty.List[TextFile], True),
        (list[TextFile], list[EncodedText], False),
        (list[TextFile], TextFile, False),
        (TextFile, list[TextFile], False),
        # Unions are never considered coercible (a runtime converter is required)
        (EncodedText | TextFile, TextFile, False),
        (TextFile, EncodedText | TextFile, False),
    ],
)
def test_is_coercible(t: type, u: type, expected: bool) -> None:
    assert is_coercible(t, u) is expected


def test_pipeline_validates_union_field_datatypes(work_dir: Path) -> None:
    """Checks that the input/output validators of a pipeline bound to a frameset can
    handle union datatypes on the pipeline fields, which the builtin issubclass
    can't be passed as its first argument"""
    bp = TestDatasetBlueprint(
        hierarchy=["abcd"],
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file", datatype=TextFile, filenames=["file.txt"]),
        ],
    )
    frameset = bp.make_dataset(FileSystem(), str(work_dir / "dataset"))
    frameset.add_source("file", TextFile)
    frameset.add_sink("out", TextFile)

    frameset.apply(
        "a_pipeline",
        EncodedTextIdentity(),
        inputs=[("file", "in_file", EncodedText | TextFile)],
        outputs=[("out", "out_file", EncodedText | TextFile)],
    )

    pipeline = frameset.pipelines["a_pipeline"]
    assert pipeline.inputs[0].datatype == EncodedText | TextFile
    assert pipeline.outputs[0].datatype == EncodedText | TextFile


@pytest.mark.parametrize(
    ("source_datatype", "input_datatype", "output_datatype"),
    [
        pytest.param(
            EncodedText.convertible_from(),
            EncodedText | None,
            EncodedText,
            id="union-column-optional-input",
        ),
        pytest.param(
            # e.g. the optional inputs of an XNAT container service command
            ty.Optional[EncodedText.convertible_from()],
            EncodedText | None,
            EncodedText,
            id="optional-union-column-optional-input",
        ),
        pytest.param(
            TextFile,
            EncodedText | None,
            EncodedText,
            id="fixed-column-optional-input",
        ),
        pytest.param(
            TextFile | None,
            EncodedText | None,
            EncodedText,
            id="optional-fixed-column-optional-input",
        ),
        pytest.param(
            TextFile,
            EncodedText,
            EncodedText | None,
            id="optional-output",
        ),
        pytest.param(
            ty.Optional[EncodedText.convertible_from()],
            EncodedText | None,
            EncodedText | None,
            id="optional-union-column-optional-input-and-output",
        ),
    ],
)
def test_pipeline_optional_field_datatypes(
    source_datatype: type,
    input_datatype: type,
    output_datatype: type,
    work_dir: Path,
) -> None:
    """Checks that optional datatypes (i.e. unions with None) on pipeline fields and
    source columns are handled when the stored format needs to be converted, both
    when constructing the pipeline (validators) and at runtime (converters)"""
    bp = TestDatasetBlueprint(
        hierarchy=["abcd"],
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file", datatype=TextFile, filenames=["file.txt"]),
        ],
    )
    frameset = bp.make_dataset(FileSystem(), str(work_dir / "dataset"))
    frameset.add_source("file", source_datatype)
    frameset.add_sink("out", TextFile)

    frameset.apply(
        "a_pipeline",
        OptionalEncodedTextIdentity(),
        inputs=[("file", "in_file", input_datatype)],
        outputs=[("out", "out_file", output_datatype)],
    )

    out = next(iter(frameset.derive("out", cache_dir=work_dir / "cache")[0]))
    assert out.raw_contents == "file.txt"


@pytest.mark.parametrize(
    "datatype",
    [
        EncodedText,
        EncodedText | None,
        ty.Optional[EncodedText],
    ],
)
def test_runtime_converter_workflow_optional_datatype(
    datatype: type, work_dir: Path
) -> None:
    """Runs the runtime converter workflow used for union column datatypes directly,
    to check that optional target datatypes are handled without needing to set up a
    dataset"""
    in_file = TextFile.sample(work_dir / "in")
    in_file.write_text("file.txt")
    outputs = RuntimeConverterWorkflow(
        in_file=in_file, datatype=datatype, converter_args={}
    )(cache_root=work_dir / "cache", worker="debug")
    assert isinstance(outputs.out_file, EncodedText)
    assert outputs.out_file.raw_contents != "file.txt"


def test_pipeline_generic_column_with_specific_input(work_dir: Path) -> None:
    """Checks that an input datatype that is more specific than the datatype of its
    column (here `EncodedText` from a `UnicodeFile` column) is converted if the stored
    item isn't already of that datatype, rather than being passed to pydra unconverted,
    which could only cast it as one if it already was (i.e. not a '.txt' file)"""
    bp = TestDatasetBlueprint(
        hierarchy=["abcd"],
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file", datatype=TextFile, filenames=["file.txt"]),
        ],
    )
    frameset = bp.make_dataset(FileSystem(), str(work_dir / "dataset"))
    frameset.add_source("file", UnicodeFile)
    frameset.add_sink("out", TextFile)

    frameset.apply(
        "a_pipeline",
        EncodedTextIdentity(),
        inputs=[("file", "in_file", EncodedText)],
        outputs=[("out", "out_file", EncodedText)],
    )

    out = next(iter(frameset.derive("out", cache_dir=work_dir / "cache")[0]))
    # converted to EncodedText for the pipeline, and back to TextFile to be stored
    assert out.raw_contents == "file.txt"


@pytest.mark.parametrize(
    ("sink_datatype", "converted"),
    [
        pytest.param(EncodedText, True, id="needs-conversion"),
        pytest.param(TextFile, False, id="already-matches"),
    ],
)
def test_pipeline_generic_output_with_specific_column(
    sink_datatype: type, converted: bool, work_dir: Path
) -> None:
    """Checks that a pipeline output with a datatype that is more generic than the
    datatype of its column (here `UnicodeFile`) is converted to the column's datatype
    if the output item isn't already of that datatype, rather than being passed to
    pydra unconverted, which could only cast it if it already was"""
    bp = TestDatasetBlueprint(
        hierarchy=["abcd"],
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file", datatype=TextFile, filenames=["file.txt"]),
        ],
    )
    frameset = bp.make_dataset(FileSystem(), str(work_dir / "dataset"))
    frameset.add_source("file", TextFile)
    frameset.add_sink("out", sink_datatype)

    frameset.apply(
        "a_pipeline",
        GenericTextOutput(),
        inputs=[("file", "in_file", TextFile)],
        outputs=[("out", "out_file", UnicodeFile)],
    )

    out = next(iter(frameset.derive("out", cache_dir=work_dir / "cache")[0]))
    assert isinstance(out, sink_datatype)
    assert (out.raw_contents != "file.txt") is converted


def test_pipeline_union_output(work_dir: Path) -> None:
    """Checks that a pipeline output with a union datatype is converted to the
    datatype of its column at runtime, depending on which member the item is"""
    bp = TestDatasetBlueprint(
        hierarchy=["abcd"],
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file", datatype=TextFile, filenames=["file.txt"]),
        ],
    )
    frameset = bp.make_dataset(FileSystem(), str(work_dir / "dataset"))
    frameset.add_source("file", TextFile)
    frameset.add_sink("out", TextFile)

    frameset.apply(
        "a_pipeline",
        UnionTextOutput(),
        inputs=[("file", "in_file", EncodedText)],
        outputs=[("out", "out_file", EncodedText | TextFile)],
    )

    out = next(iter(frameset.derive("out", cache_dir=work_dir / "cache")[0]))
    # converted to EncodedText for the input, and back to TextFile to be stored
    assert type(out) is TextFile
    assert out.raw_contents == "file.txt"


def test_pipeline_union_column_with_generic_superclass(work_dir: Path) -> None:
    """Checks that a source column whose union datatype includes a generic superclass
    ahead of the stored item's actual type (as `FileSet.convertible_from()` can produce
    when it sorts the union by class name, e.g. `ImageFormatGz | MedicalImage | ... |
    NiftiXBvec`) still resolves the item to its most specific type, so that the
    registered converter for that type is used instead of the raw files being passed
    through to a pipeline input that is a subclass of the generic type"""
    bp = TestDatasetBlueprint(
        hierarchy=["abcd"],
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file", datatype=TextFile, filenames=["file.txt"]),
        ],
    )
    frameset = bp.make_dataset(FileSystem(), str(work_dir / "dataset"))
    # `File` is a superclass of `EncodedText`, the input datatype of the pipeline
    frameset.add_source("file", File | EncodedText | TextFile)
    frameset.add_sink("out", TextFile)

    frameset.apply(
        "a_pipeline",
        EncodedTextIdentity(),
        inputs=[("file", "in_file", EncodedText)],
        outputs=[("out", "out_file", EncodedText)],
    )

    out = next(iter(frameset.derive("out", cache_dir=work_dir / "cache")[0]))
    assert out.raw_contents == "file.txt"


@pytest.mark.parametrize(
    "source_datatype",
    [
        pytest.param(TextFile, id="fixed-column"),  # converter selected at build time
        pytest.param(
            EncodedText.convertible_from(), id="union-column"
        ),  # converter selected at runtime
    ],
)
def test_pipeline_optional_input_already_matches(
    source_datatype: type, work_dir: Path
) -> None:
    """Checks that an optional pipeline input (e.g. `TextFile | None`) is sourced
    without conversion when the stored item already is of the required type, i.e.
    when `get_converter()` returns None to signify that no converter is needed"""
    bp = TestDatasetBlueprint(
        hierarchy=["abcd"],
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file", datatype=TextFile, filenames=["file.txt"]),
        ],
    )
    frameset = bp.make_dataset(FileSystem(), str(work_dir / "dataset"))
    frameset.add_source("file", source_datatype)
    frameset.add_sink("out", TextFile)

    frameset.apply(
        "a_pipeline",
        OptionalTextIdentity(),
        inputs=[("file", "in_file", TextFile | None)],
        outputs=[("out", "out_file", TextFile | None)],
    )

    out = next(iter(frameset.derive("out", cache_dir=work_dir / "cache")[0]))
    assert out.raw_contents == "file.txt"


@pytest.mark.parametrize("datatype", [TextFile | None, File | None, File])
def test_runtime_converter_workflow_already_matches(
    datatype: type, work_dir: Path
) -> None:
    """Checks that the runtime converter workflow passes the input through unchanged
    when it already matches the (optional) target datatype"""
    in_file = TextFile.sample(work_dir / "in")
    in_file.write_text("file.txt")
    outputs = RuntimeConverterWorkflow(
        in_file=in_file, datatype=datatype, converter_args={}
    )(cache_root=work_dir / "cache", worker="debug")
    assert isinstance(outputs.out_file, TextFile)
    assert outputs.out_file.raw_contents == "file.txt"


def test_runtime_converter_workflow_validates_generic_input(work_dir: Path) -> None:
    """Checks that an input of a generic type is validated against the target
    datatype rather than being assumed to match it because the target is a subclass
    of the input's type"""
    in_file = TextFile.sample(work_dir / "in")
    in_file.write_text("file.txt")
    generic = File(in_file)
    # The generic file is a valid TextFile so it can be passed through as one
    outputs = RuntimeConverterWorkflow(
        in_file=generic, datatype=TextFile | None, converter_args={}
    )(cache_root=work_dir / "cache-1", worker="debug")
    assert type(outputs.out_file) is TextFile
    # but it isn't a valid EncodedText, so it shouldn't be passed through as one, but
    # identified as a TextFile to find the converter for it, as converters aren't
    # registered for generic types
    outputs = RuntimeConverterWorkflow(
        in_file=generic, datatype=EncodedText, converter_args={}
    )(cache_root=work_dir / "cache-2", worker="debug")
    assert isinstance(outputs.out_file, EncodedText)
    assert outputs.out_file.raw_contents != "file.txt"


@pytest.mark.parametrize("datatype", [Foo, Foo | None, ty.Optional[Foo]])
def test_runtime_converter_workflow_no_converter(
    datatype: type, work_dir: Path
) -> None:
    """Checks that a missing converter is reported as a FormatConversionError, including
    when the target datatype is optional (i.e. the `NoneType` member of the union is
    skipped rather than queried for a converter)"""
    in_file = TextFile.sample(work_dir / "in")
    in_file.write_text("file.txt")
    with pytest.raises(
        FormatConversionError, match="Failed to get converter"
    ) as excinfo:
        RuntimeConverterWorkflow(in_file=in_file, datatype=datatype, converter_args={})(
            cache_root=work_dir / "cache", worker="debug"
        )
    assert "NoneType" not in str(excinfo.value)

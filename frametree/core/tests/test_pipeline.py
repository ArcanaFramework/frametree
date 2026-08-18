import typing as ty
from pathlib import Path

from fileformats.extras.testing import EncodedFromTextConverter, EncodedToTextConverter
from fileformats.testing import EncodedText
from fileformats.text import TextFile
from pydra.compose import python

from frametree.core.frameset.base import FrameSet
from frametree.core.pipeline import RuntimeConverterWorkflow
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
def ConcatenateEncodedText(in_files: ty.List[EncodedText]) -> TextFile:
    # Every item should have already been converted from the stored TextFile
    # format to EncodedText (i.e. shifted) by a per-item converter task before
    # reaching here, so none of them should still read as the original contents
    assert all(f.raw_contents != "file.txt" for f in in_files)
    out_file = TextFile.sample()
    out_file.write_text("\n".join(f.raw_contents for f in in_files))
    return out_file


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

from fileformats.extras.testing import EncodedToTextConverter
from fileformats.testing import EncodedText
from fileformats.text import TextFile
from pydra.compose import python

from frametree.core.pipeline import RuntimeConverterWorkflow
from frametree.file_system import FileSystem
from frametree.testing import TestAxes
from frametree.testing.blueprint import FileSetEntryBlueprint as FileBP
from frametree.testing.blueprint import TestDatasetBlueprint


@python.define(outputs=["out_file"])
def EncodedTextIdentity(in_file: EncodedText) -> EncodedText:
    assert in_file.raw_contents != "file.txt"
    return in_file


def test_pipeline_union_column_datatype(saved_dataset, data_store, work_dir):

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

    out = next(iter(frameset.derive("out")[0]))
    assert out.raw_contents == "file.txt"

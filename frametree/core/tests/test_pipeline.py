from fileformats.testing import EncodedText
from fileformats.text import Plain as PlainText
from pydra.compose import python

from frametree.file_system import FileSystem
from frametree.testing import TestAxes
from frametree.testing.blueprint import FileSetEntryBlueprint as FileBP
from frametree.testing.blueprint import TestDatasetBlueprint


@python.define
def EncodedTextIdentity(in_file: EncodedText) -> EncodedText:
    return in_file


def test_pipeline_union_column_datatype(saved_dataset, data_store, work_dir):

    bp = TestDatasetBlueprint(
        hierarchy=[
            "abcd"
        ],  # e.g. XNAT where session ID is unique in project but final layer is organised by visit
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file", datatype=PlainText, filenames=["file.txt"]),
        ],
    )
    frameset = bp.make_dataset(FileSystem(), str(work_dir / "dataset"))
    frameset.add_source(
        "file",
        EncodedText.convertible_from(),
    )
    frameset.add_sink(
        "out",
        PlainText,
    )

    # Start generating the arguments for the CLI
    # Add source to loaded dataset

    frameset.apply(
        "a_pipeline",
        EncodedTextIdentity,
        inputs={
            (
                "file",
                "in_file",
                PlainText,
            )
        },
        outputs=[
            (
                "out",
                "out_file",
                PlainText,
            )
        ],
    )

    workflow = frameset.pipeline("a_pipeline")()
    assert workflow

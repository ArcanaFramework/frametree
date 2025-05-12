from operator import mul
from pathlib import Path
from functools import reduce
from fileformats.core import FileSet
from fileformats.text import TextFile
from fileformats.field import Text, Boolean
from frametree.common import FileSystem
from frametree.testing.blueprint import (
    TestDatasetBlueprint,
    TestAxes,
    FileSetEntryBlueprint,
    FieldEntryBlueprint,
)
from frametree.core.frameset.base import FrameSet


def test_column_api_access(dataset: FrameSet):

    bp = dataset.__annotations__["blueprint"]

    for fileset_bp in bp.entries:

        dataset.add_source(fileset_bp.path, fileset_bp.datatype)

        col = dataset[fileset_bp.path]

        # Check length of column
        assert len(col) == reduce(mul, bp.dim_lengths)

        # Access file-set via leaf IDs
        with dataset.tree:
            for id_ in col.ids:
                item = col[id_]
                assert isinstance(item, fileset_bp.datatype)
                if issubclass(fileset_bp.datatype, FileSet):
                    assert sorted(p.name for p in item.fspaths) == sorted(
                        fileset_bp.filenames
                    )


def test_column_datatype_conversion(tmp_path: Path):
    # Check that the datatype conversion works
    frameset = TestDatasetBlueprint(  # dataset name
        axes=TestAxes,
        hierarchy=["a", "b", "c", "d"],
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileSetEntryBlueprint(
                path="file1", datatype=TextFile, filenames=["file.txt"]
            ),
            FieldEntryBlueprint(
                path="textfield",
                row_frequency="abcd",
                datatype=Text,
                value="sample-text",
            ),  # Derivatives to insert
            FieldEntryBlueprint(
                path="booleanfield",
                row_frequency="c",
                datatype=Boolean,
                value="no",
                expected_value=False,
            ),  # Derivatives to insert
        ],
    ).make_dataset(
        store=FileSystem(),
        dataset_id=tmp_path / "field-datatype-conversion",
        name="",
    )  # type: ignore[no-any-return]

    ID_KEY = ("a0", "b0", "c0", "d0")

    frameset.add_source("text_file", "text/text-file", path="file1")
    frameset.add_source("text_field", str, path="textfield")
    frameset.add_source("boolean_field", bool, path="booleanfield")
    assert [p.name for p in frameset["text_file"][ID_KEY].fspaths] == ["file1.txt"]
    assert frameset["text_field"][ID_KEY].value == "sample-text"
    assert frameset["boolean_field"][ID_KEY].value is False

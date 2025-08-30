import operator as op
from itertools import chain
from functools import reduce, partial
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count
from typing import Any, Type
import pytest
from fileformats.generic import File
from fileformats.text import TextFile
from fileformats.field import Text as TextField
from frametree.core.frameset.base import FrameSet
from frametree.core.store import Store
from frametree.core.entry import DataEntry
from frametree.core.serialize import asdict
from frametree.file_system import FileSystem
from frametree.testing.blueprint import (
    TestDatasetBlueprint,
    FileSetEntryBlueprint as FileBP,
    FieldEntryBlueprint as FieldBP,
)
from fileformats.text import Plain as PlainText
from frametree.testing import MockRemote, TestAxes, MockRemote


def test_populate_tree(dataset: FrameSet) -> None:
    blueprint = dataset.__annotations__["blueprint"]
    for freq in dataset.axes:
        # For all non-zero bases in the row_frequency, multiply the dim lengths
        # together to get the combined number of rows expected for that
        # row_frequency
        num_rows = reduce(
            op.mul, (ln for ln, b in zip(blueprint.dim_lengths, freq) if b), 1
        )
        assert (
            len(dataset.rows(str(freq))) == num_rows
        ), f"{freq} doesn't match {len(dataset.rows(str(freq)))} vs {num_rows}"


def test_populate_row(dataset: FrameSet) -> None:
    blueprint = dataset.__annotations__["blueprint"]
    for row in dataset.rows("abcd"):
        if isinstance(dataset.store, FileSystem):
            expected_paths = sorted(
                chain(
                    (e.path for e in blueprint.entries if isinstance(e, FieldBP)),
                    *(e.filenames for e in blueprint.entries if isinstance(e, FileBP)),
                )
            )
        else:
            expected_paths = sorted(e.path for e in blueprint.entries)
        entry_paths = sorted(e.path for e in row.entries)
        assert entry_paths == expected_paths


def test_get(dataset: FrameSet) -> None:
    blueprint = dataset.__annotations__["blueprint"]
    for entry_bp in blueprint.entries:
        dataset.add_source(entry_bp.path, datatype=entry_bp.datatype)
    for row in dataset.rows(str(dataset.leaf_freq)):
        for entry_bp in blueprint.entries:
            item = row[entry_bp.path]
            if item.is_fileset:
                item.trim_paths()  # type: ignore[attr-defined]
                assert sorted(p.name for p in item.fspaths) == sorted(  # type: ignore[attr-defined]
                    entry_bp.filenames
                )
            else:
                assert item.value == entry_bp.expected_value  # type: ignore[attr-defined]


def test_post(dataset: FrameSet) -> None:
    blueprint = dataset.__annotations__["blueprint"]

    def check_inserted() -> None:
        """Check that the inserted items are present in the dataset"""
        for deriv_bp in blueprint.derivatives:  # name, freq, datatype, _
            for row in dataset.rows(deriv_bp.row_frequency):
                cell = row.cell(deriv_bp.path, allow_empty=False)
                item = cell.item
                if item.is_fileset and isinstance(dataset.store, FileSystem):
                    assert item.fspath.relative_to(dataset.id)  # type: ignore
                assert isinstance(item, deriv_bp.datatype)
                if deriv_bp.datatype.is_fileset:
                    assert item.hash_files() == all_checksums[deriv_bp.path]  # type: ignore[attr-defined]
                else:
                    assert item.primitive(item.value) == item.primitive(  # type: ignore[attr-defined]
                        deriv_bp.expected_value
                    )

    all_checksums = {}
    with dataset.tree:
        for deriv_bp in blueprint.derivatives:  # name, freq, datatype, files
            dataset.add_sink(
                name=deriv_bp.path,
                datatype=deriv_bp.datatype,
                row_frequency=deriv_bp.row_frequency,
            )
            test_file = deriv_bp.make_item()
            if deriv_bp.datatype.is_fileset:
                all_checksums[deriv_bp.path] = test_file.hash_files()
            # Test inserting the new item into the store
            with dataset.tree:
                for row in dataset.rows(deriv_bp.row_frequency):
                    row[deriv_bp.path] = test_file
        check_inserted()  # Check that cached objects have been updated
    check_inserted()  # Check that objects can be recreated from store


def test_frameset_roundtrip(dataset: FrameSet) -> None:
    definition = asdict(dataset, omit=["store", "name"])
    definition["store-version"] = "1.0.0"

    data_store = dataset.store

    with data_store.connection:
        data_store.save_frameset_definition(
            dataset_id=dataset.id, definition=definition, name="test_dataset"
        )
        reloaded_definition = data_store.load_frameset_definition(
            dataset_id=dataset.id, name="test_dataset"
        )
    assert definition == reloaded_definition


# We use __file__ here as we just need any old file and can guarantee it exists
@pytest.mark.parametrize("datatype,value", [(File, __file__), (TextField, "value")])
def test_provenance_roundtrip(
    datatype: Type[Any], value: str, saved_dataset: FrameSet
) -> None:
    provenance = {"a": 1, "b": [1, 2, 3], "c": {"x": True, "y": "foo", "z": "bar"}}
    data_store = saved_dataset.store

    with data_store.connection:
        entry = data_store.create_entry("provtest@", datatype, saved_dataset.root)
        data_store.put(datatype(value), entry)  # Create the entry first
        data_store.put_provenance(provenance, entry)  # Save the provenance
        reloaded_provenance = data_store.get_provenance(entry)  # reload the provenance
        assert provenance == reloaded_provenance


def test_singletons() -> None:
    standard = set(["file_system"])
    assert set(Store.singletons()) & standard == standard  # type: ignore[call-overload]


@pytest.mark.skipif(
    condition=cpu_count() < 2, reason="Not enough cpus to run test with multiprocessing"
)
def test_delayed_download(
    delayed_mock_remote: MockRemote, simple_dataset_blueprint: TestDatasetBlueprint
) -> None:

    dataset_id = "delayed_download"
    dataset = simple_dataset_blueprint.make_dataset(delayed_mock_remote, dataset_id)
    entry = next(iter(dataset.rows())).entry("file1")

    delayed_mock_remote.clear_cache()

    worker = partial(
        delayed_download,
        entry,
    )
    with Pool(2) as p:
        try:
            no_offset, with_offset = p.map(worker, [0.0, 0.001])
        finally:
            p.close()  # Marks the pool as closed.
            p.join()  # Required to get the concurrency to show up in test coverage

    assert no_offset == "file1.txt"
    assert with_offset == "modified"


def delayed_download(entry: DataEntry, start_offset: float) -> str:
    # Set the downloads off at slightly different times
    time.sleep(start_offset)
    text_file = TextFile(entry.item)  # type: ignore[arg-type]
    contents: str = text_file.raw_contents
    if not start_offset:
        with open(text_file.fspath, "w") as f:
            f.write("modified")
    return contents


def test_entry_access(tmp_path: Path) -> None:

    cache_dir = tmp_path / "mock-remote-store" / "cache"
    remote_dir = tmp_path / "mock-remote-store" / "remote"
    cache_dir.mkdir(parents=True, exist_ok=True)
    remote_dir.mkdir(parents=True, exist_ok=True)

    store = MockRemote(
        server="http://a.server.com",
        cache_dir=cache_dir,
        user="admin",
        password="admin",
        remote_dir=remote_dir,
    )

    blueprint = TestDatasetBlueprint(
        hierarchy=[
            "abcd"
        ],  # e.g. XNAT where session ID is unique in project but final layer is organised by visit
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file1", datatype=PlainText, filenames=["1.txt"], order_key=1),
            FileBP(path="file1", datatype=PlainText, filenames=["2.txt"], order_key=2),
        ],
    )

    dataset_id = "delayed_download"
    dataset: FrameSet = blueprint.make_dataset(store, dataset_id)
    row = dataset.row(id="a0b0c0d0", frequency=TestAxes.abcd)
    assert PlainText(row.entry("file1", order=0).item).contents == "1.txt"
    assert PlainText(row.entry("file1", order=1).item).contents == "2.txt"
    assert PlainText(row.entry("file1", order=-1).item).contents == "2.txt"
    assert PlainText(row.entry("file1", order=-2).item).contents == "1.txt"
    assert PlainText(row.entry("file1", key="1").item).contents == "1.txt"
    assert PlainText(row.entry("file1", key="2").item).contents == "2.txt"
    with pytest.raises(ValueError):
        row.entry("file1", order=0, key="0")

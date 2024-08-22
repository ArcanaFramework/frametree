from pathlib import Path
import pytest
from frametree.core.frameset.base import FrameSet
from frametree.core.salience import ColumnSalience
from frametree.core.quality import DataQuality
from frametree.testing import TestAxes
from frametree.core.cli.frameset import (
    define,
    add_source,
    add_sink,
    missing_items,
    export,
)
from fileformats.text import TextFile
from fileformats.generic import Directory
from frametree.core.utils import show_cli_trace
from frametree.testing.blueprint import TEST_DATASET_BLUEPRINTS
from frametree.testing import MockRemote
from frametree.common import FileSystem


ARBITRARY_INTS_A = [234221, 93380, 43271, 137483, 30009, 214205, 363526]
ARBITRARY_INTS_B = [353726, 29202, 32867, 129872, 12281, 776524, 908763]


def get_arbitrary_slice(i, dim_length):
    a = ARBITRARY_INTS_A[i] % dim_length
    b = ARBITRARY_INTS_B[i] % dim_length
    lower = min(a, b)
    upper = max(a, b) + 1
    return lower, upper


def test_add_column_cli(saved_dataset: FrameSet, cli_runner):
    # Get CLI name for dataset (i.e. file system path prepended by 'file_system//')
    # Add source to loaded dataset
    saved_dataset.add_source(
        name="a_source",
        path="file1",
        datatype=TextFile,
        row_frequency=TestAxes.d,
        quality_threshold=DataQuality.questionable,
        order=1,
        required_metadata={},
        is_regex=False,
    )
    # Add source column to saved dataset
    result = cli_runner(
        add_source,
        [
            saved_dataset.locator,
            "a_source",
            "text/text-file",
            "--path",
            "file1",
            "--row-frequency",
            "d",
            "--quality",
            "questionable",
            "--order",
            "1",
            "--no-regex",
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    # Add source to loaded dataset
    saved_dataset.add_sink(
        name="a_sink",
        path="deriv",
        datatype=TextFile,
        row_frequency=TestAxes.d,
        salience=ColumnSalience.qa,
    )
    result = cli_runner(
        add_sink,
        [
            saved_dataset.locator,
            "a_sink",
            "text/text-file",
            "--path",
            "deriv",
            "--row-frequency",
            "d",
            "--salience",
            "qa",
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    # Reload the saved dataset and check the parameters were saved/loaded
    # correctly
    loaded_dataset = FrameSet.load(saved_dataset.locator)
    assert saved_dataset.columns == loaded_dataset.columns


@pytest.mark.skip("Not implemented")
def test_add_missing_items_cli(saved_dataset: FrameSet, cli_runner):
    result = cli_runner(missing_items, [])
    assert result.exit_code == 0, show_cli_trace(result)


def test_define_cli(dataset: FrameSet, cli_runner):
    blueprint = dataset.__annotations__["blueprint"]
    # Get CLI name for dataset (i.e. file system path prepended by 'file//')
    path = dataset.locator
    # Start generating the arguments for the CLI
    args = list(blueprint.hierarchy)
    # Generate "arbitrary" values for included and excluded from dim length
    # and index
    included = {}
    excluded = {}
    for i, (dim_length, axis) in enumerate(zip(blueprint.dim_lengths, dataset.axes)):
        a, b = get_arbitrary_slice(i, dim_length)
        if i % 2:
            included[str(axis)] = f"{a}:{b}"
        elif str(axis) in dataset.hierarchy:  # Check that we aren't excluding all
            excluded[str(axis)] = f"{a}:{b}"
    # Add include and exclude options
    for axis, slce in included.items():
        args.extend(["--include", axis, slce])
    for axis, slce in excluded.items():
        args.extend(["--exclude", axis, slce])
    args.extend(["--axes", "frametree.testing:TestAxes"])
    # Run the command line
    result = cli_runner(define, [path, *args])
    # Check tool completed successfully
    assert result.exit_code == 0, show_cli_trace(result)
    # Reload the saved dataset and check the parameters were saved/loaded
    # correctly
    loaded_dataset = FrameSet.load(path)
    assert loaded_dataset.hierarchy == blueprint.hierarchy
    assert loaded_dataset.include == included
    assert loaded_dataset.exclude == excluded


def test_export_import_roundtrip(cli_runner, work_dir: Path, frametree_home):
    blueprint = TEST_DATASET_BLUEPRINTS["skip_single"]
    cache_dir = work_dir / "remote-cache"
    cache_dir.mkdir()
    remote_dir = work_dir / "remote-dir"
    remote_dir.mkdir()
    mock_remote = MockRemote(
        server="https://a.server.com",
        user="admin",
        password="admin",
        cache_dir=work_dir / "remote-cache",
        remote_dir=remote_dir,
    )
    mock_remote.save("my_mock_remote")
    original = blueprint.make_dataset(store=mock_remote, dataset_id="original")
    original.add_sink(
        name="doubledir1",
        datatype=Directory,
        path="doubledir1",
    )
    original.add_sink(
        name="doubledir2",
        datatype=Directory,
        path="doubledir2",
    )
    original.save()
    local_dataset_id = str(work_dir / "exported")
    # Add source column to saved dataset
    result = cli_runner(
        export,
        [
            original.locator,
            "file_system",
            local_dataset_id,
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    local_dataset = FileSystem().load_frameset(local_dataset_id)
    result = cli_runner(
        export,
        [
            local_dataset.locator,
            "my_mock_remote",
            "reimported",
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    reimported = mock_remote.load_frameset("reimported")
    reimported.id = "original"
    assert reimported == original

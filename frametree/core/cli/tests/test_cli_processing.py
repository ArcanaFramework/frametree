from functools import reduce
from operator import mul
from frametree.core.utils import show_cli_trace
from fileformats.text import TextFile
from pathlib import Path
import tempfile
import pytest
from frametree.core.frameset import FrameSet
from frametree.core.cli.processing import install_license
from frametree.core.cli.processing import derive, apply
from frametree.testing import MockRemote


def test_apply_cli(saved_dataset: FrameSet, ConcatenateTask, cli_runner):
    # Get CLI name for dataset (i.e. file system path prepended by 'file_system//')
    # Start generating the arguments for the CLI
    # Add source to loaded dataset
    duplicates = 5
    saved_dataset.add_source("file1", TextFile)
    saved_dataset.add_source("file2", TextFile)
    saved_dataset.add_sink("concatenated", TextFile)
    saved_dataset.apply(
        name="a_pipeline",
        task=ConcatenateTask(duplicates=duplicates),
        inputs=[("file1", "in_file1"), ("file2", "in_file2")],
        outputs=[("concatenated", "out_file")],
    )
    # Add source column to saved dataset
    result = cli_runner(
        apply,
        [
            saved_dataset.locator,
            "a_pipeline",
            "frametree.testing.tasks:" + ConcatenateTask.__name__,
            "--source",
            "file1",
            "in_file1",
            "text/text-file",
            "--source",
            "file2",
            "in_file2",
            "text/text-file",
            "--sink",
            "concatenated",
            "out_file",
            "text/text-file",
            "--parameter",
            "duplicates",
            str(duplicates),
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    loaded_dataset = FrameSet.load(saved_dataset.locator)
    assert saved_dataset.pipelines == loaded_dataset.pipelines


def test_derive_cli(saved_dataset, ConcatenateTask, cli_runner):
    # Get CLI name for dataset (i.e. file system path prepended by 'file//')
    bp = saved_dataset.__annotations__["blueprint"]
    duplicates = 3
    # Start generating the arguments for the CLI
    # Add source to loaded dataset
    result = cli_runner(
        apply,
        [
            saved_dataset.locator,
            "a_pipeline",
            "frametree.testing.tasks:" + ConcatenateTask.__name__,
            "--source",
            "file1",
            "in_file1",
            "text/text-file",
            "--source",
            "file2",
            "in_file2",
            "text/text-file",
            "--sink",
            "concatenated",
            "out_file",
            "text/text-file",
            "--parameter",
            "duplicates",
            str(duplicates),
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    # Add source column to saved dataset
    result = cli_runner(
        derive, [saved_dataset.locator, "concatenated", "--plugin", "debug"]
    )
    assert result.exit_code == 0, show_cli_trace(result)
    sink = saved_dataset.add_sink("concatenated", TextFile)
    assert len(sink) == reduce(mul, bp.dim_lengths)
    fnames = ["file1.txt", "file2.txt"]
    if ConcatenateTask.__name__.endswith("Reverse"):
        fnames = [f[::-1] for f in fnames]
    expected_contents = "\n".join(fnames * duplicates)
    for item in sink:
        with open(item) as f:
            contents = f.read()
        assert contents == expected_contents


LICENSE_CONTENTS = "test license"


@pytest.fixture(scope="module")
def test_license():
    tmp_dir = Path(tempfile.mkdtemp())
    test_license = tmp_dir / "license.txt"
    test_license.write_text(LICENSE_CONTENTS)
    return str(test_license)


def test_cli_install_dataset_license(
    saved_dataset: FrameSet, test_license, frametree_home, cli_runner, tmp_path
):
    store_nickname = saved_dataset.id + "_store"
    license_name = "test-license"
    saved_dataset.store.save(store_nickname)
    address = store_nickname + "//" + saved_dataset.id + "@" + saved_dataset.name

    result = cli_runner(
        install_license,
        [
            license_name,
            test_license,
            address,
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    assert saved_dataset.get_license_file(license_name).contents == LICENSE_CONTENTS

    # Test overwriting
    new_contents = "new_contents"
    new_license = tmp_path / "new-license.txt"
    new_license.write_text(new_contents)

    result = cli_runner(
        install_license,
        [
            license_name,
            str(new_license),
            address,
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    assert saved_dataset.get_license_file(license_name).contents == new_contents


def test_cli_install_site_license(
    data_store,
    test_license: str,
    frametree_home,
    cli_runner,
):
    store_nickname = "site_license_store"
    license_name = "test-license"
    data_store.save(store_nickname)

    if isinstance(data_store, MockRemote):
        env = {
            data_store.SITE_LICENSES_USER_ENV: "arbitrary_user",
            data_store.SITE_LICENSES_PASS_ENV: "arbitrary_password",
        }
    else:
        env = {}

    result = cli_runner(
        install_license,
        [
            license_name,
            test_license,
            store_nickname,
        ],
        env=env,
    )

    assert result.exit_code == 0, show_cli_trace(result)

    assert (
        data_store.get_site_license_file(
            license_name, user="arbitrary_user", password="arbitrary_password"
        ).contents
        == LICENSE_CONTENTS
    )

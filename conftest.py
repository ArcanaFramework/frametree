import os
import logging
from pathlib import Path
import typing as ty
from datetime import datetime
import shutil
from tempfile import mkdtemp
from unittest.mock import patch
import pytest
from click.testing import CliRunner
from pydra.compose.base import Task
from frametree.core.frameset import FrameSet
from frametree.core.store import Store
from fileformats.text import Plain as PlainText
from frametree.testing.tasks import (
    Concatenate,
    ConcatenateReverse,
    TEST_TASKS,
    BASIC_TASKS,
)
from frametree.testing.blueprint import (
    TestDatasetBlueprint,
    FileSetEntryBlueprint as FileBP,
    TEST_DATASET_BLUEPRINTS,
    GOOD_DATASETS,
)
from frametree.testing import TestAxes, MockRemote, AlternateMockRemote
from frametree.file_system import FileSystem

# from pydra import set_input_validator

# set_input_validator(True)


# Set DEBUG logging for unittests

log_level = logging.WARNING

logger = logging.getLogger("frametree")
logger.setLevel(log_level)

sch = logging.StreamHandler()
sch.setLevel(log_level)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
sch.setFormatter(formatter)
logger.addHandler(sch)

PKG_DIR = Path(__file__).parent


@pytest.fixture
def work_dir() -> Path:  # type: ignore[misc]
    # work_dir = Path.home() / '.frametree-tests'
    # work_dir.mkdir(exist_ok=True)
    # return work_dir
    work_dir = mkdtemp()
    yield Path(work_dir)
    # shutil.rmtree(work_dir)


@pytest.fixture(scope="session")
def build_cache_dir() -> Path:
    # build_cache_dir = Path.home() / '.frametree-test-build-cache'
    # if build_cache_dir.exists():
    #     shutil.rmtree(build_cache_dir)
    # build_cache_dir.mkdir()
    return Path(mkdtemp())
    # return build_cache_dir


@pytest.fixture
def cli_runner(catch_cli_exceptions: bool) -> ty.Callable[..., ty.Any]:
    def invoke(
        *args: ty.Any, catch_exceptions: bool = catch_cli_exceptions, **kwargs: ty.Any
    ) -> ty.Any:
        runner = CliRunner()
        result = runner.invoke(*args, catch_exceptions=catch_exceptions, **kwargs)  # type: ignore[misc]
        return result

    return invoke


@pytest.fixture(scope="session")
def pkg_dir() -> Path:
    return PKG_DIR


@pytest.fixture(scope="session")
def run_prefix() -> str:
    "A datetime string used to avoid stale data left over from previous tests"
    return datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")


# For debugging in IDE's don't catch raised exceptions and let the IDE
# break at it
if os.getenv("_PYTEST_RAISE", "0") != "0":

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call: pytest.CallInfo[ty.Any]) -> None:
        if call.excinfo is not None:
            raise call.excinfo.value

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo: pytest.ExceptionInfo[BaseException]) -> None:
        raise excinfo.value

    CATCH_CLI_EXCEPTIONS = False
else:
    CATCH_CLI_EXCEPTIONS = True


@pytest.fixture
def catch_cli_exceptions() -> bool:
    return CATCH_CLI_EXCEPTIONS


@pytest.fixture(params=BASIC_TASKS)
def pydra_task_details(request: pytest.FixtureRequest) -> ty.Tuple[str, ty.Any]:
    func_name = request.param
    return ("frametree.analysis.tasks.tests.fixtures" + func_name,) + tuple(
        TEST_TASKS[func_name][1:]
    )


@pytest.fixture(params=BASIC_TASKS)
def pydra_task(request: pytest.FixtureRequest) -> Task:
    task, args, expected_out = TEST_TASKS[request.param]
    task.test_args = args  # stash args away in task object for future access
    return task


# ------------------------------------
# Pytest fixtures and helper functions
# ------------------------------------

DATA_STORES = ["file_system", "mock_remote"]


@pytest.fixture(scope="session")
def frametree_home() -> ty.Generator[Path, None, None]:
    frametree_home = Path(mkdtemp()) / "frametree-home"
    with patch.dict(os.environ, {"FRAMETREE_HOME": str(frametree_home)}):
        yield frametree_home


@pytest.fixture(params=DATA_STORES)
def data_store(
    work_dir: Path, frametree_home: Path, request: ty.Any
) -> ty.Generator[Store, None, None]:
    store: Store
    if request.param == "file_system":
        store = FileSystem()
    elif request.param.endswith("mock_remote"):
        cache_dir = work_dir / "mock-remote-store" / "cache"
        cache_dir.mkdir(parents=True)
        remote_dir = work_dir / "mock-remote-store" / "remote"
        remote_dir.mkdir(parents=True)
        klass = (
            AlternateMockRemote if request.param == "alt_mock_remote" else MockRemote
        )
        store = klass(
            server="http://a.server.com",
            cache_dir=cache_dir,
            user="admin",
            password="admin",
            remote_dir=remote_dir,
        )
        store.save("test_mock_store")
    else:
        assert False, f"Unrecognised store {request.param}"
    yield store


@pytest.fixture
def delayed_mock_remote(
    work_dir: Path,
    frametree_home: Path,  # So we save the store definition in the home dir, not ~/.frametree
) -> MockRemote:
    cache_dir = work_dir / "mock-remote-store" / "cache"
    cache_dir.mkdir(parents=True)
    remote_dir = work_dir / "mock-remote-store" / "remote"
    remote_dir.mkdir(parents=True)
    store = MockRemote(
        server="http://a.server.com",
        cache_dir=cache_dir,
        user="admin",
        password="admin",
        remote_dir=remote_dir,
        mock_delay=0.1,
    )
    store_name = "delayed_mock_remote"
    store.save(store_name)
    return store


@pytest.fixture(params=GOOD_DATASETS)
def dataset(
    work_dir: Path, data_store: Store, request: pytest.FixtureRequest
) -> ty.Generator[FrameSet, None, None]:
    dataset_name = request.param
    blueprint = TEST_DATASET_BLUEPRINTS[dataset_name]
    dataset_path = work_dir / dataset_name
    dataset_id = dataset_path if isinstance(data_store, FileSystem) else dataset_name
    dataset = blueprint.make_dataset(data_store, dataset_id)
    yield dataset
    # shutil.rmtree(dataset.id)


@pytest.fixture
def simple_dataset_blueprint() -> TestDatasetBlueprint:
    return TestDatasetBlueprint(
        hierarchy=[
            "abcd"
        ],  # e.g. XNAT where session ID is unique in project but final layer is organised by visit
        axes=TestAxes,
        dim_lengths=[1, 1, 1, 1],
        entries=[
            FileBP(path="file1", datatype=PlainText, filenames=["file1.txt"]),
            FileBP(path="file2", datatype=PlainText, filenames=["file2.txt"]),
        ],
    )


@pytest.fixture
def saved_dataset(
    data_store: Store, simple_dataset_blueprint: TestDatasetBlueprint, work_dir: Path
) -> FrameSet:
    if isinstance(data_store, FileSystem):
        dataset_id = str(work_dir / "saved-dataset")
    else:
        dataset_id = "saved_dataset"
    return simple_dataset_blueprint.make_dataset(
        data_store, dataset_id, name=""
    )  # type: ignore[no-any-return]


@pytest.fixture
def tmp_dir() -> ty.Generator[Path, None, None]:
    tmp_dir = Path(mkdtemp())
    yield tmp_dir
    shutil.rmtree(tmp_dir)


@pytest.fixture(params=["forward", "reverse"])
def ConcatenateTask(request: pytest.FixtureRequest) -> Task:
    if request.param == "forward":
        task = Concatenate
    else:
        task = ConcatenateReverse
    return task

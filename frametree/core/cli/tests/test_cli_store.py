from frametree.core.cli.store import add, ls, remove, rename
from frametree.core.utils import show_cli_trace
from frametree.core.store import Store

STORE_URI = "http://dummy.uri"
STORE_USER = "a_user"
STORE_PASSWORD = "a-password"


def test_store_cli(cli_runner, frametree_home, work_dir):
    store_name = "test-mock-remote"
    # Add new XNAT configuration
    result = cli_runner(
        add,
        [
            "testing:MockRemote",
            store_name,
            "--server",
            STORE_URI,
            "--user",
            STORE_USER,
            "--password",
            STORE_PASSWORD,
            "--option",
            "remote_dir",
            str(work_dir / "remote-dir"),
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    # List all saved and built-in stores
    result = cli_runner(ls, [])
    assert result.exit_code == 0, show_cli_trace(result)
    assert f"{store_name} - frametree.testing.store:MockRemote" in result.output
    assert "    server: " + STORE_URI in result.output


def test_store_cli_remove(cli_runner, frametree_home, work_dir):
    new_store_name = "a-new-mock"
    # Add new XNAT configuration
    cli_runner(
        add,
        [
            "testing:MockRemote",
            new_store_name,
            "--server",
            STORE_URI,
            "--user",
            STORE_USER,
            "--password",
            STORE_PASSWORD,
            "--option",
            "remote_dir",
            str(work_dir / "remote-dir"),
        ],
    )
    # Check store is saved
    result = cli_runner(ls, [])
    assert new_store_name in result.output

    cli_runner(remove, new_store_name)
    # Check store is gone
    result = cli_runner(ls, [])
    assert new_store_name not in result.output


def test_store_cli_rename(cli_runner, frametree_home, work_dir):
    old_store_name = "i123"
    new_store_name = "y456"
    # Add new XNAT configuration
    cli_runner(
        add,
        [
            "testing:MockRemote",
            old_store_name,
            "--server",
            STORE_URI,
            "--user",
            STORE_USER,
            "--password",
            STORE_PASSWORD,
            "--option",
            "remote_dir",
            str(work_dir / "remote-dir"),
        ],
    )
    # Check store is saved
    result = cli_runner(ls, [])
    assert "i123 - frametree.testing.store:MockRemote" in result.output

    cli_runner(rename, [old_store_name, new_store_name])
    # Check store is renamed
    result = cli_runner(ls, [])
    assert "i123 - frametree.testing.store:MockRemote" not in result.output
    assert "y456 - frametree.testing.store:MockRemote" in result.output


def test_store_cli_encrypt_credentials(cli_runner, frametree_home, work_dir):
    store_name = "another-test-mock"
    # Add new XNAT configuration
    result = cli_runner(
        add,
        [
            "testing:MockRemote",
            store_name,
            "--server",
            STORE_URI,
            "--user",
            STORE_USER,
            "--password",
            STORE_PASSWORD,
            "--option",
            "remote_dir",
            str(work_dir / "remote-dir"),
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    # Check credentials have been encrypted
    loaded_store = Store.load(store_name)
    assert loaded_store.password != ""
    assert loaded_store.password is not STORE_PASSWORD
    assert loaded_store.user != ""
    assert loaded_store.user is not STORE_USER

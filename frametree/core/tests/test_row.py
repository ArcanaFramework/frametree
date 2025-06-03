from pydra.utils.hash import hash_single, Cache
from fileformats.generic import File
from frametree.testing import MockRemote
from frametree.core.frameset import FrameSet


def test_row_hash(saved_dataset: FrameSet) -> None:
    """Test that hashes of rows are consistent across different runs."""
    row = list(saved_dataset.rows())[0]
    hsh = hash_single(row, Cache())
    if isinstance(saved_dataset, MockRemote):
        assert hsh == b'\xe6"&\xd1D\xb0\xf6\xfc\x8b\xf9\xca\xd4\xda\xa7V\xac'
    row.create_entry("dummy", File)
    hsh2 = hash_single(row, Cache())
    assert hsh2 == hsh, "Hash should not change after adding an entry to the row."

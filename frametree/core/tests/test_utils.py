import re
import pytest
from frametree.core.packaging import package_from_module
from frametree.core.utils import path2varname, varname2path


def test_package_from_module():
    assert package_from_module("frametree.core").key == "frametree"
    assert package_from_module("pydra.engine").key == "pydra"


PATHS_TO_TEST = [
    "dwi/dir-LR_dwi",
    "func/task-rest_bold",
    "with spaces and___ underscores",
    "__a.very$illy*ath~",
    "anat/T1w",
    "anat___l___T1w",
    "_u__u_",
]


@pytest.mark.parametrize("path", PATHS_TO_TEST)
def test_path2varname(path: str):
    varname = path2varname(path)
    assert re.match(r"^\w+$", varname)
    assert varname2path(varname) == path


@pytest.mark.parametrize("path", PATHS_TO_TEST)
def test_triple_path2varname(path: str):
    assert (
        varname2path(
            varname2path(varname2path(path2varname(path2varname(path2varname(path)))))
        )
        == path
    )

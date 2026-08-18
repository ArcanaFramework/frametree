import re
import typing as ty

import pytest
from fileformats.application import Atfx, Dicom
from fileformats.image import Png, RasterImage

from frametree.core.packaging import package_from_module
from frametree.core.utils import convertible_from, path2varname, varname2path


def test_package_from_module():
    assert package_from_module("frametree.core").name == "frametree"
    assert package_from_module("pydra.engine").name == "pydra"


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


@pytest.mark.parametrize(
    ["klass", "expected"],
    [
        (Png, Png | RasterImage),
        (Png | None, Png | RasterImage | None),
        (Dicom | Png, Dicom | Png | RasterImage),
        (Atfx, Atfx),
        # A list of a type (e.g. items gathered from several rows by a
        # coarser-frequency pipeline, see `frametree.core.pipeline.SourceItems`) is
        # convertible from a list of whatever the element type is convertible from
        (ty.List[Png], ty.List[Png | RasterImage]),
    ],
)
def test_convertible_from(klass, expected):
    assert convertible_from(klass) == expected

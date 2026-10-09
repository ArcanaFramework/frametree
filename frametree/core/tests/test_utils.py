import re
import typing as ty

import pytest
from pydra.utils.typing import is_union
from fileformats.application import Atfx, Dicom
from fileformats.core import FileSet, to_mime
from fileformats.generic import Directory, DirectoryOf, File
from fileformats.text import TextFile
from fileformats.image import Png, RasterImage

from frametree.core.packaging import package_from_module
from frametree.core.utils import (
    convertible_from,
    path2varname,
    resource_fspaths,
    varname2path,
)


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


def make_resource(resource_dir, entries):
    for entry in entries:
        if entry.endswith("/"):
            (resource_dir / entry).mkdir(parents=True)
            (resource_dir / entry / "file.txt").write_text("file")
        else:
            resource_dir.mkdir(parents=True, exist_ok=True)
            (resource_dir / entry).write_text("file")
    return resource_dir


@pytest.mark.parametrize(
    "datatype", [Directory, Directory | None, DirectoryOf[TextFile]]
)
def test_resource_fspaths_directory_contents_at_root(datatype, tmp_path):
    """The contents of a directory stored at the root of the resource directory"""
    resource_dir = make_resource(tmp_path / "res", ["sub1/", "sub2/", "log.txt"])
    assert resource_fspaths(resource_dir, datatype) == [resource_dir]


def test_resource_fspaths_nested_directory(tmp_path):
    """A directory nested within the resource directory, as stored by sink columns"""
    resource_dir = make_resource(tmp_path / "res", ["bundle/"])
    assert resource_fspaths(resource_dir, Directory) == [resource_dir / "bundle"]


@pytest.mark.parametrize("datatype", [FileSet, File, TextFile])
def test_resource_fspaths_non_directory_types(datatype, tmp_path):
    """The contents of the resource are returned unchanged for non-directory types"""
    resource_dir = make_resource(tmp_path / "res", ["sub1/", "log.txt"])
    assert sorted(resource_fspaths(resource_dir, datatype)) == sorted(
        resource_dir.iterdir()
    )


def test_convertible_from_drops_wildcard_types():
    """Generic converters (e.g. from `SetOf[T]` to `DirectoryOf[T]`) register source
    types with "wildcard" classifiers, which can't be used as concrete datatypes, e.g.
    to generate the MIME-like types of the inputs of an XNAT command"""
    conv_from = convertible_from(FileSet)
    members = ty.get_args(conv_from) if is_union(conv_from) else (conv_from,)
    assert FileSet in members
    assert not any(
        hasattr(t, "wildcard_classifiers") and t.wildcard_classifiers() for t in members
    )
    to_mime(conv_from, official=False)  # shouldn't raise

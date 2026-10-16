import re
import typing as ty

import pytest
from fileformats.application import Atfx
from fileformats.core import from_mime, to_mime
from fileformats.core.exceptions import FormatMismatchError
from fileformats.generic import File, UnicodeFile
from fileformats.image import Png, RasterImage
from fileformats.testing import EncodedText, Foo
from fileformats.text import TextFile

from frametree.core.packaging import package_from_module
from frametree.core.utils import (
    convertible_from,
    path2varname,
    strip_annotated,
    to_datatype,
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
        # Testing formats, which don't have converters registered by other packages
        (Foo | EncodedText, Foo | TextFile | EncodedText),
        (Atfx, Atfx),
        # A list of a type (e.g. items gathered from several rows by a
        # coarser-frequency pipeline, see `frametree.core.pipeline.SourceItems`) is
        # convertible from a list of whatever the element type is convertible from
        (ty.List[Png], list[Png | RasterImage]),
    ],
)
def test_convertible_from(klass, expected):
    assert strip_annotated(convertible_from(klass)) == expected


@pytest.mark.parametrize(
    ["klass", "mime"],
    [
        (Png, "image/png+convertible-to"),
        (Png | None, "image/png+convertible-to?"),
        (
            Atfx | Png,
            "application/atfx+convertible-to|image/png+convertible-to",
        ),
        (ty.List[Png], "image/png+convertible-to+list-of"),
    ],
)
def test_convertible_from_mime_roundtrip(klass, mime):
    conv_from = convertible_from(klass)
    assert to_mime(conv_from, official=False) == mime
    # NB: lists are read as `list[...]` instead of `typing.List[...]`
    assert to_mime(from_mime(mime), official=False) == mime
    assert strip_annotated(from_mime(mime)) == strip_annotated(conv_from)
    assert convertible_from(klass) == expected


@pytest.mark.parametrize(
    "datatype",
    [
        # `FileSet.convertible_from()` sorts its union by class name, so a generic
        # superclass with a registered converter (e.g. `MedicalImage`, which can be
        # converted to `ImageFormatGz`) can come before the more specific type the
        # item actually is (e.g. `NiftiXBvec`)
        File | TextFile,
        TextFile | File,
        File | UnicodeFile | TextFile,
        File | EncodedText | TextFile,
        TextFile | None,
        File | TextFile | None,
    ],
)
def test_to_datatype_union_picks_most_specific(datatype: type, tmp_path) -> None:
    fspath = tmp_path / "file.txt"
    fspath.write_text("file.txt")
    assert type(to_datatype(fspath, datatype)) is TextFile


def test_to_datatype_union_falls_back_to_generic(tmp_path) -> None:
    fspath = tmp_path / "file.txt"
    fspath.write_text("file.txt")
    # EncodedText doesn't match a '.txt' file, so the generic type is the best match
    assert type(to_datatype(fspath, EncodedText | File)) is File


def test_to_datatype_union_no_match(tmp_path) -> None:
    fspath = tmp_path / "file.txt"
    fspath.write_text("file.txt")
    with pytest.raises(FormatMismatchError):
        to_datatype(fspath, EncodedText | Png)

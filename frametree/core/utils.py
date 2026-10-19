from __future__ import annotations

import difflib
import functools
import inspect
import logging
import operator
import os.path
import re
import subprocess as sp
import traceback
import typing as ty
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType, UnionType

import attrs
import cloudpickle as cp
import pydra.compose.base
import yaml
from fileformats.core import DataType, FieldPrimitive, FileSet, FileSetPrimitive
from fileformats.core.exceptions import FormatMismatchError
from pydra.utils.typing import is_optional, is_union, optional_type

from frametree.core.exceptions import FrameTreeError, FrameTreeUsageError

logger = logging.getLogger("frametree")


PIPELINE_ANNOTATIONS = "__frametree_pipeline__"
CONVERTER_ANNOTATIONS = "__frametree_converter__"
SWICTH_ANNOTATIONS = "__frametree_switch__"
CHECK_ANNOTATIONS = "__frametree_check__"

FRAMETREE_SPEC = "__frametree_type__"


PATH_SUFFIX = "_path"
FIELD_SUFFIX = "_field"
CHECKSUM_SUFFIX = "_checksum"

FRAMETREE_HOME_DIR = Path.home() / ".frametree"

FRAMETREE_PIP = "git+ssh://git@github.com/australian-imaging-service/frametree.git"

HASH_CHUNK_SIZE = 2**20  # 1MB in calc. checksums to avoid mem. issues


@attrs.define
class NestedContext:
    """Base class for "nested contexts", which can be used in "with" statements at
    at multiple points in the API, and ensures that the context is only entered at most
    once at any one point. This allows low level calls to ensure that they are executing
    within an appropriate context, while also enabling high level calls to maintain a
    context over multiple low-level calls, and thereby not take the performance hit of
    continually setting up and breaking down the context.

    Parameters
    -----------
    _type_
        _description_
    """

    depth: int = attrs.field(default=0, init=False)

    def __enter__(self) -> ty.Self:
        # This allows the store to be used within nested contexts
        # but still only use one connection. This is useful for calling
        # methods that need connections, and therefore control their
        # own connection, in batches using the same connection by
        # placing the groupedvisit calls within an outer context.
        self.depth += 1
        if self.depth == 1:
            self.enter()
        return self

    def __exit__(
        self,
        exception_type: ty.Optional[ty.Type[BaseException]],
        exception_value: ty.Optional[BaseException],
        traceback: ty.Optional[TracebackType],
    ) -> None:
        self.depth -= 1
        if self.depth == 0:
            self.exit()

    def enter(self) -> None:
        "To be overridden in subclasses as necessary"
        pass

    def exit(self) -> None:
        "To be overridden in subclasses as necessary"
        pass


def get_home_dir() -> Path:
    try:
        home_dir = Path(os.environ["FRAMETREE_HOME"])
    except KeyError:
        home_dir = FRAMETREE_HOME_DIR
    if not home_dir.exists():
        home_dir.mkdir()
    return home_dir


def get_config_file_path(name: str) -> Path:
    """Gets the file path for the configuration file corresponding to `name`

    Parameters
    ----------
    name
        Name of the configuration file to return

    Returns
    -------
    Path
        Path to configuration file
    """
    return get_home_dir() / (name + ".yaml")


# Escape values for invalid characters for Python variable names
PATH_ESCAPES = {
    "___": "x___x",
    "/": "___l___",
    ".": "___o___",
    " ": "___s___",
    "\t": "___t___",
    ",": "___comma___",
    ">": "___gt___",
    "<": "___lt___",
    "-": "___H___",
    "'": "___singlequote___",
    '"': "___doublequote___",
    "(": "___openparens___",
    ")": "___closeparens___",
    "[": "___openbracket___",
    "]": "___closebracket___",
    "{": "___openbrace___",
    "}": "___closebrace___",
    ":": "___colon___",
    ";": "___semicolon___",
    "`": "___tick___",
    "~": "___tilde___",
    "|": "___pipe___",
    "?": "___question___",
    "\\": "___backslash___",
    "$": "___dollar___",
    "@": "___at___",
    "!": "___exclaimation___",
    "#": "___pound___",
    "%": "___percent___",
    "^": "___caret___",
    "&": "___ampersand___",
    "*": "___star___",
    "+": "___plus___",
    "=": "___equals___",
    "XXX": "___tripleX___",
}

# As long as no escape sequences start or end with the beginning or end of the triple
# underscore escape 'x___x' then it should always be reversible
assert not any(e.startswith("___x") and e.endswith("x___") for e in PATH_ESCAPES)

PATH_NAME_PREFIX = "XXX"

EMPTY_PATH_NAME = "___empty___"


def path2varname(path: str) -> str:
    """Escape a string (typically a file-system path) so that it can be used as a Python
    variable name by replacing non-valid characters with escape sequences in PATH_ESCAPES.

    Parameters
    ----------
    path : str
        A path containing '/' characters that need to be escaped

    Returns
    -------
    str
        A python safe name
    """
    if not path:
        name = EMPTY_PATH_NAME
    else:
        name = path
        for char, esc in PATH_ESCAPES.items():
            name = name.replace(char, esc)
    if name.startswith("_"):
        name = PATH_NAME_PREFIX + name
    return name


def varname2path(name: str) -> str:
    """Unescape a Pythonic name created by `path2varname`

    Parameters
    ----------
    name : str
        the escaped path

    Returns
    -------
    str
        the original path
    """
    if name.startswith(PATH_NAME_PREFIX):
        path = name[len(PATH_NAME_PREFIX) :]
    else:
        path = name  # strip path-name prefix
    if path == EMPTY_PATH_NAME:
        return ""
    # the order needs to be reversed so that "dunder" (double underscore) is
    # unescaped last
    for char, esc in reversed(PATH_ESCAPES.items()):
        path = path.replace(esc, char)
    return path


def path2label(path: str) -> str:
    return path2varname(path.rstrip("@"))


def label2path(label: str) -> str:
    path = varname2path(label)
    if "@" not in path:
        path += "@"
    return path


def set_loggers(
    loglevel: str, pydra_level: str = "warning", depend_level: str = "warning"
) -> None:
    """Sets loggers for frametree and pydra. To be used in CLI

    Parameters
    ----------
    loglevel : str
        the threshold to produce logs at (e.g. debug, info, warning, error)
    pydra_level : str, optional
        the threshold to produce logs from Pydra at
    depend_level : str, optional
        the threshold to produce logs in dependency packages
    """

    def parse(level: str) -> str:
        if isinstance(level, str):
            level = getattr(logging, level.upper())
        return level

    logging.getLogger("frametree").setLevel(parse(loglevel))
    logging.getLogger("pydra").setLevel(parse(pydra_level))

    # set logging format
    logging.basicConfig(level=parse(depend_level))


@contextmanager
def set_cwd(path: str) -> ty.Iterator[str]:
    """Sets the current working directory to `path` and back to original
    working directory on exit

    Parameters
    ----------
    path : str
        The file system path to set as the current working directory
    """
    pwd = os.getcwd()
    os.chdir(path)
    try:
        yield path
    finally:
        os.chdir(pwd)


def dir_modtime(dpath: str) -> float:
    """
    Returns the latest modification time of all files/subdirectories in a
    directory
    """
    return max(os.path.getmtime(d) for d, _, _ in os.walk(dpath))


def iscontainer(*items: ty.Any) -> bool:
    """
    Checks whether all the provided items are containers (i.e of class list,
    dict, tuple, etc...)
    """
    return all(isinstance(i, Iterable) and not isinstance(i, str) for i in items)


# def find_mismatch(first, second, indent=""):
#     """
#     Finds where two objects differ, iterating down into nested containers
#     (i.e. dicts, lists and tuples) They can be nested containers
#     any combination of primary formats, str, int, float, dict and lists

#     Parameters
#     ----------
#     first : dict | list | tuple | str | int | float
#         The first object to compare
#     second : dict | list | tuple | str | int | float
#         The other object to compare with the first
#     indent : str
#         The amount newlines in the output string should be indented. Provide
#         the actual indent, i.e. a string of spaces.

#     Returns
#     -------
#     mismatch : str
#         Human readable output highlighting where two container differ.
#     """

#     # Basic case where we are dealing with non-containers
#     if not (isinstance(first, type(second)) or isinstance(second, type(first))):
#         mismatch = " types: self={} v other={}".format(
#             type(first).__name__, type(second).__name__
#         )
#     elif not iscontainer(first, second):
#         mismatch = ": self={} v other={}".format(first, second)
#     else:
#         sub_indent = indent + "  "
#         mismatch = ""
#         if isinstance(first, dict):
#             if sorted(first.keys()) != sorted(second.keys()):
#                 mismatch += " keys: self={} v other={}".format(
#                     sorted(first.keys()), sorted(second.keys())
#                 )
#             else:
#                 mismatch += ":"
#                 for k in first:
#                     if first[k] != second[k]:
#                         mismatch += "\n{indent}'{}' values{}".format(
#                             k,
#                             find_mismatch(first[k], second[k], indent=sub_indent),
#                             indent=sub_indent,
#                         )
#         else:
#             mismatch += ":"
#             for i, (f, s) in enumerate(zip_longest(first, second)):
#                 if f != s:
#                     mismatch += "\n{indent}{} index{}".format(
#                         i, find_mismatch(f, s, indent=sub_indent), indent=sub_indent
#                     )
#     return mismatch


def wrap_text(
    text: str, line_length: int, indent: int, prefix_indent: bool = False
) -> str:
    """
    Wraps a text block to the specified line-length, without breaking across
    words, using the specified indent to join the lines

    Parameters
    ----------
    text : str
        The text to wrap
    line_length : int
        The desired line-length for the wrapped text (including indent)
    indent : int
        The number of spaces to use as an indent for the wrapped lines
    prefix_indent : bool
        Whether to prefix the indent to the wrapped text

    Returns
    -------
    wrapped : str
        The wrapped text
    """
    lines = []
    nchars = line_length - indent
    if nchars <= 0:
        raise FrameTreeUsageError(
            "In order to wrap text, the indent cannot be larger than the " "line-length"
        )
    while text:
        if len(text) > nchars:
            n = text[:nchars].rfind(" ")
            if n < 1:
                next_space = text[nchars:].find(" ")
                if next_space < 0:
                    # No spaces found
                    n = len(text)
                else:
                    n = nchars + next_space
        else:
            n = nchars
        lines.append(text[:n])
        text = text[(n + 1) :]
    wrapped = "\n{}".format(" " * indent).join(lines)
    if prefix_indent:
        wrapped = " " * indent + wrapped
    return wrapped


class classproperty(object):
    def __init__(self, f: ty.Callable[..., ty.Any]) -> None:
        self.f = f

    def __get__(self, obj: object, owner: object) -> ty.Any:
        return self.f(owner)


extract_import_re = re.compile(r"\s*(?:from|import)\s+([\w\.]+)")

NOTHING_STR = "__PIPELINE_INPUT__"


def show_workflow_errors(
    pipeline_cache_dir: Path, omit_nodes: ty.Collection[str] = ()
) -> str:
    """Extract nodes with errors and display results

    Parameters
    ----------
    pipeline_cache_dir : Path
        the path container the pipeline cache directories
    omit_nodes : collection[str], optional
        The names of the nodes to omit from the error message

    Returns
    -------
    str
        a string displaying the error messages
    """
    # PKL_FILES = ["_task.pklz", "_result.pklz", "_error.pklz"]
    out_str = ""

    def load_contents(fpath: Path) -> ty.Optional[pydra.compose.base.Task]:
        contents = None
        if fpath.exists():
            with open(fpath, "rb") as f:
                contents = cp.load(f)
        return contents

    for path in pipeline_cache_dir.iterdir():
        if not path.is_dir():
            continue
        if "_error.pklz" in [p.name for p in path.iterdir()]:
            task = load_contents(path / "_task.pklz")
            if not task or task.name in omit_nodes:
                continue
            if task:
                out_str += f"{task.name} ({type(task)}):\n"
                out_str += "    inputs:"
                for inpt_name in task.input_names:
                    out_str += (
                        f"\n        {inpt_name}: {getattr(task.inputs, inpt_name)}"
                    )
                try:
                    out_str += "\n\n    cmdline: " + task.cmdline
                except Exception:
                    pass
            else:
                out_str += "Anonymous task:\n"
            error = load_contents(path / "_error.pklz")
            if error:
                out_str += "\n\n    errors:\n"
                for k, v in error.items():
                    if k == "error message":
                        indent = "            "
                        out_str += (
                            "        message:\n"
                            + indent
                            + "".join(ln.replace("\n", "\n" + indent) for ln in v)
                        )
                    else:
                        out_str += f"        {k}: {v}\n"
    return out_str


def add_exc_note(e: Exception, note: str) -> Exception:
    """Adds a note to an exception in a Python <3.11 compatible way

    Parameters
    ----------
    e : Exception
        the exception to add the note to
    note : str
        the note to add

    Returns
    -------
    Exception
        returns the exception again
    """
    if hasattr(e, "add_note"):
        e.add_note(note)
    else:
        e.args = (e.args[0] + "\n" + note,)
    return e


def dict_diff(
    dict1: ty.Dict[ty.Any, ty.Any],
    dict2: ty.Dict[ty.Any, ty.Any],
    label1: str = "dict1",
    label2: str = "dict2",
) -> str:
    """Create a human readable diff between two dictionaries

    Parameters
    ----------
    dict1 : dict
        first dictionary to compare
    dict2 : dict
        second dictionary to compare
    label1 : str
        label to give first dictionary in diff
    label2 : str
        label to give second dictionary in diff

    Returns
    -------
    diff : str
        the unified diff between the two dictionaries
    """
    yaml1 = yaml.dump(dict1, sort_keys=True, indent=4)
    yaml2 = yaml.dump(dict2, sort_keys=True, indent=4)
    diff = difflib.unified_diff(
        yaml1.splitlines(),
        yaml2.splitlines(),
        fromfile=label1,
        tofile=label2,
        lineterm="\n",
    )
    return "\n".join(diff)


def full_path(fspath: ty.Union[str, Path]) -> Path:
    return Path(fspath).resolve().absolute()


DT = ty.TypeVar("DT", bound=DataType)


def to_datatype(
    item: DataType | FileSetPrimitive | FieldPrimitive, datatype: ty.Type[DT]
) -> DT:
    """Casts a given item into the specified datatype, handling optional and union types

    Parameters
    ----------
    item : DataType | FileSetPrimitive | FieldPrimitive
        the item to convert
    datatype : ty.Type[DT]
        the datatype to convert the item to

    Returns
    -------
    DataType
        the converted item
    """
    datatype = strip_annotated(datatype)
    if is_optional(datatype):
        if item is None:
            return None
        datatype = optional_type(datatype)

    if is_union(datatype):
        # Try all the types in the union, rather than just returning the first match,
        # so the most specific type that matches can be selected. Otherwise, a generic
        # type that happens to appear earlier in the union (e.g. `MedicalImage` in
        # `ImageFormatGz.convertible_from()`, which is sorted by class name) would be
        # selected over the more specific type of the item (e.g. `NiftiXBvec`), and the
        # converter registered for the specific type would be missed.
        matches = []
        for tp in ty.get_args(datatype):
            try:
                matches.append(to_datatype(item, tp))
            except FormatMismatchError:
                pass
        if not matches:
            raise FormatMismatchError(
                f"Item {item} could not be converted to any of the union types {datatype}"
            )
        # Drop matches for which there is a match of a more specific (sub)type, keeping
        # the union order otherwise
        most_specific = [
            m
            for m in matches
            if not any(
                type(o) is not type(m) and issubclass(type(o), type(m)) for o in matches
            )
        ]
        return most_specific[0]

    return datatype(item)


def strip_annotated(type_: ty.Any) -> ty.Any:
    """Strips the metadata from `typing.Annotated` types, including those nested within
    unions and the arguments of generic types, e.g. ``Annotated[A | B, meta] | None``
    is stripped to ``A | B | None``. Types without any annotations are returned as is

    Parameters
    ----------
    type_ : type
        the type to strip the annotations from

    Returns
    -------
    type
        the type without the annotations
    """
    origin = ty.get_origin(type_)
    if origin is None:
        return type_
    args = ty.get_args(type_)
    if origin is ty.Annotated:
        return strip_annotated(args[0])
    stripped = tuple(strip_annotated(a) for a in args)
    if all(s is a for s, a in zip(stripped, args)):
        return type_
    if origin in (ty.Union, UnionType):
        return ty.Union[stripped]  # flattens the unions that were annotated
    try:
        return origin[stripped]
    except TypeError:
        return type_


def is_directory_type(datatype: ty.Any) -> bool:
    """Whether the datatype, or any member of a union/optional datatype, is a directory
    type (e.g. `Directory`, `DirectoryOf[...]`)"""
    from fileformats.generic import Directory

    types = ty.get_args(datatype) if is_union(datatype) else (datatype,)
    return any(isinstance(t, type) and issubclass(t, Directory) for t in types)


def resource_fspaths(
    resource_dir: Path, datatype: ty.Any, fspaths: ty.Optional[ty.List[Path]] = None
) -> ty.List[Path]:
    """Selects the file-system paths of an item stored in a "resource" directory (e.g. an
    XNAT resource) to be passed to the item's datatype.

    Remote stores return the contents of the resource directory, which works for most
    datatypes and for directories stored by sink columns (which are nested within the
    resource). However, a resource can also hold the contents of a directory at its
    root (e.g. if it was uploaded with `xnat`'s `upload_dir(<dir>)`). In that case the
    contents won't match a directory datatype but the resource directory itself will,
    so it is returned instead.

    Parameters
    ----------
    resource_dir : Path
        the directory holding the item
    datatype : type
        the datatype the item will be loaded as
    fspaths : list[Path], optional
        the paths within the resource directory that make up the item, by default all
        of its contents

    Returns
    -------
    list[Path]
        the paths to pass to the datatype
    """
    if fspaths is None:
        fspaths = list(resource_dir.iterdir())
    if not is_directory_type(datatype):
        return fspaths
    try:
        to_datatype(fspaths, datatype)
    except FormatMismatchError:
        try:
            to_datatype([resource_dir], datatype)
        except FormatMismatchError:
            pass  # neither match, so leave it to the caller to report the mismatch
        else:
            return [resource_dir]
    return fspaths


def convertible_from(datatype: ty.Type[DataType]) -> ty.Any:
    """Determine the types that can be converted into the given datatype or union of
    datatypes, annotated with the datatypes they were determined from (see
    `fileformats.core.ConvertibleTo`) so that they are written to MIME-like strings as
    "<namespace>/<format>+convertible-to", and determined again from the converters
    that are installed when the string is read. Use `strip_annotated`
    to get the union of the types themselves.

    Parameters
    ----------
    datatype : ty.Type[DataType]
        the datatype to check

    Returns
    -------
    type
        the annotated union of datatypes that can be converted into the given datatype
    """
    if ty.get_origin(datatype) is ty.Annotated:
        return datatype  # e.g. already the types that a datatype is convertible from
    if is_union(datatype):
        # Includes optional types, the annotated types aren't flattened into a
        # single union so the datatype each was determined from is retained
        return functools.reduce(
            operator.or_,
            (
                tp if tp is type(None) else convertible_from(tp)
                for tp in ty.get_args(datatype)
            ),
        )
    if ty.get_origin(datatype) is list:
        # A list of a fileset/field type (e.g. items gathered from several rows by a
        # coarser-frequency pipeline, see `frametree.core.pipeline.SourceItems`) is
        # convertible from a list of whatever the element type is convertible from
        (elem_type,) = ty.get_args(datatype)
        conv_from = ty.List[convertible_from(elem_type)]  # type: ignore[valid-type]
    elif issubclass(datatype, FileSet):
        conv_from = datatype.convertible_from()
        if is_union(conv_from):
            # Drop types with "wildcard" classifiers (e.g. `DirectoryOf[T]`), which are
            # the source types of generic converters that can't be used as concrete
            # datatypes (e.g. they don't have a MIME-like type)
            concrete = [
                t
                for t in ty.get_args(conv_from)
                if not (hasattr(t, "wildcard_classifiers") and t.wildcard_classifiers())
            ]
            conv_from = functools.reduce(operator.or_, concrete)
    else:
        conv_from = datatype
    if optional:
        conv_from |= None
    return conv_from


class fromdict_converter:
    def __init__(self, tp: ty.Type[ty.Any]):
        try:
            self.container_type = tp.__origin__
        except AttributeError:
            self.type = tp
            self.container_type = None
        else:
            if self.container_type not in (list, tuple, set, frozenset):
                raise FrameTreeError(
                    f"generic aliases of {self.container_type} type are not supported by "
                    "fromdict_converter"
                )
            self.type = tp.__args__[0]

    def __call__(self, to_convert: ty.Any) -> ty.Any:
        if self.container_type:
            converted = self.container_type(
                self.type(**d) if isinstance(d, dict) else d for d in to_convert
            )
        else:
            converted = (
                self.type(**to_convert) if isinstance(to_convert, dict) else to_convert
            )
        return converted


def show_cli_trace(result: ty.Any) -> str:
    "Used in testing to show traceback of CLI output"
    return "".join(traceback.format_exception(*result.exc_info))


def append_suffix(path: Path, suffix: str) -> Path:
    "Appends a string suffix to a Path object"
    return Path(str(path) + suffix)


# Minimum version of FrameTree that this version can read the serialisation from
MIN_SERIAL_VERSION = "0.0.0"

# Global flag to allow references to classes to be missing from the


package_dir = os.path.join(os.path.dirname(__file__), "..")
HOSTNAME: ty.Optional[str]
try:
    HOSTNAME = sp.check_output("hostname").strip().decode("utf-8")
except sp.CalledProcessError:
    HOSTNAME = None
JSON_ENCODING = {"encoding": "utf-8"}

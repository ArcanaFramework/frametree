import shutil
from pathlib import Path
import typing as ty
import attrs
from pydra import mark, Workflow
import fileformats.core
from fileformats.generic import File
import fileformats.text
from frametree.core.row import DataRow


@mark.task
def add(a: float, b: float) -> float:
    return a + b


@mark.task
@mark.annotate({"dpath": Path, "fname": str, "return": {"path": str, "suffix": str}})
def path_manip(dpath, fname):
    path = dpath / fname
    return str(path), path.suffix


@attrs.define(auto_attribs=True)
class A:
    x: int
    y: int


@attrs.define(auto_attribs=True)
class B:
    u: float
    v: float


@attrs.define(auto_attribs=True)
class C:
    z: float


@mark.task
@mark.annotate({"a": A, "b": B, "return": {"c": C}})
def attrs_func(a, b):
    return C(z=a.x * b.u + a.y * b.v)


@mark.task
@mark.annotate({"return": {"out_file": File}})
def concatenate(
    in_file1: File,
    in_file2: File,
    out_file: ty.Optional[Path] = None,
    duplicates: int = 1,
) -> Path:
    """Concatenates the contents of two files and writes them to a third

    Parameters
    ----------
    in_file1 : Path
        A text file
    in_file2 : Path
        Another text file
    out_file : Path
       The path to write the output file to

    Returns
    -------
    Path
        A text file made by concatenating the two inputs
    """
    if out_file is None:
        out_file = Path("out_file.txt").absolute()
    contents = []
    for _ in range(duplicates):
        for fname in (in_file1, in_file2):
            with open(fname) as f:
                contents.append(f.read())
    with open(out_file, "w") as f:
        f.write("\n".join(contents))
    return out_file


@mark.task
@mark.annotate({"return": {"out_file": File}})
def reverse(in_file: File, out_file: ty.Optional[Path] = None) -> File:
    """Reverses the contents of a file and outputs it to another file

    Parameters
    ----------
    in_file : Path
        A text file
    out_file : Path
       The path to write the output file to

    Returns
    -------
    Path
        A text file with reversed contents to the original
    """
    if out_file is None:
        out_file = Path("out_file.txt").absolute()
    with open(in_file) as f:
        contents = f.read()
    with open(out_file, "w") as f:
        f.write(contents[::-1])
    return out_file


def concatenate_reverse(name="concatenate_reverse", **kwargs):
    """A simple workflow that has the same signature as concatenate, but
    concatenates reversed contents of the input files instead

    Parameters
    ----------
    name : str
        name of the workflow to be created
    **kwargs
        keyword arguments passed through to the workflow init, can be any of
        the workflow's input spec, i.e. ['in_file1', 'in_file2', 'duplicates']

    Returns
    -------
    Workflow
        the workflow that
    """
    wf = Workflow(
        name=name, input_spec=["in_file1", "in_file2", "duplicates"], **kwargs
    )

    wf.add(reverse(name="reverse1", in_file=wf.lzin.in_file1))

    wf.add(reverse(name="reverse2", in_file=wf.lzin.in_file2))

    wf.add(
        concatenate(
            name="concatenate",
            in_file1=wf.reverse1.lzout.out_file,
            in_file2=wf.reverse2.lzout.out_file,
            duplicates=wf.lzin.duplicates,
        )
    )

    wf.set_output([("out_file", wf.concatenate.lzout.out_file)])

    return wf


@mark.task
def plus_10_to_filenumbers(filenumber_row: DataRow) -> None:
    """Alters the item paths within the data row, by converting them to
    an int and adding 10. Used in the test_run_pipeline_on_row_cli test.

    Parameters
    ----------
    row : DataRow
        the data row to modify
    """
    for entry in filenumber_row.entries:
        item = fileformats.text.TextFile(ty.cast(fileformats.core.FileSet, entry.item))
        new_item_stem = str(int(item.stem) + 10)
        shutil.move(item.fspath, item.fspath.parent / (new_item_stem + item.actual_ext))


@mark.task
def identity_file(in_file: File) -> File:
    return in_file


@mark.task
def identity(in_):
    return in_


@mark.task
def multiply_contents(
    in_file: File,
    multiplier: ty.Union[int, float],
    out_file: ty.Optional[Path] = None,
    dtype: type = float,
) -> File:
    """Multiplies the contents of the file, assuming that it contains numeric
    values on separate lines

    Parameters
    ----------
    in_file : Path
        path to input file to multiply the contents of
    multiplier : int or float
        the multiplier to apply to the file values
    out_file : Path
        the path to write the output file to
    dtype : type
        the type to cast the file contents to"""

    if out_file is None:
        out_file = Path("out_file.txt").absolute()

    with open(in_file) as f:
        contents = f.read()

    multiplied = []
    for line in contents.splitlines():
        multiplied.append(str(dtype(line.strip()) * multiplier))

    with open(out_file, "w") as f:
        f.write("\n".join(multiplied))

    return File(out_file)


@mark.task
def contents_are_numeric(in_file: File) -> bool:
    """Checks the contents of a file to see whether each line can be cast to a numeric
    value

    Parameters
    ----------
    in_file : Path
        the path to a text file

    Returns
    -------
    bool
        if all the lines are numeric return True
    """
    with open(in_file) as f:
        contents = f.read()
    try:
        float(contents.strip())
    except ValueError:
        return False
    return True


@mark.task
def check_license(
    expected_license_path: File,
    expected_license_contents: File,
) -> File:
    """Checks the `expected_license_path` to see if there is a file with the same contents
    as that of `expected_license_contents`

    Parameters
    ----------
    expected_license_path : File
        path to the expected license file
    expected_license_contents : File
        path containing the contents expected in the expected license file

    Returns
    -------
    File
        passes through the expected license file so the task can be connected back to the
        dataset
    """
    with open(expected_license_contents) as f:
        expected_contents = f.read()
    with open(expected_license_path) as f:
        actual_contents = f.read()
    if expected_contents != actual_contents:
        raise Exception(
            f'License contents "{actual_contents}" did not match '
            f'expected "{expected_contents}"'
        )
    return expected_license_contents


TEST_TASKS = {
    "add": (add, {"a": 4, "b": 5}, {"out": 9}),
    "path_manip": (
        path_manip,
        {"dpath": Path("/home/foo/Desktop"), "fname": "bar.txt"},
        {"path": "/home/foo/Desktop/bar.txt", "suffix": ".txt"},
    ),
    "attrs_func": (
        attrs_func,
        {"a": A(x=2, y=4), "b": B(u=2.5, v=1.25)},
        {"c": C(z=10)},
    ),
}

BASIC_TASKS = ["add", "path_manip", "attrs_func"]

FILE_TASKS = ["concatenate"]

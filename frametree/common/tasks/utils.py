import typing as ty
import json
from pydra.design import python
from pydra.engine.core import File
from fileformats.core import FileSet


def identity(**fields: ty.Any) -> ty.Tuple[ty.Any, ...]:
    return tuple(fields.values())


def define_identity(fields: ty.List[str]) -> ty.Callable:
    return python.define(identity, inputs=fields, outputs=fields)


@python.define
def IdentityConverter(in_file: FileSet) -> FileSet:
    """Returns the input file set

    Parameters
    ----------
    in_file : FileSet
        The input file set

    Returns
    -------
    out_file: FileSet
        The input file set
    """
    return in_file


@python.define
def ExtractFromJson(in_file: File, field_name: str) -> ty.Any:
    with open(in_file) as f:
        dct = json.load(f)
    return dct[field_name]  # FIXME: Should use JSONpath syntax

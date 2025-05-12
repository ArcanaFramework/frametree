from __future__ import annotations
from dataclasses import is_dataclass, fields as dataclass_fields
from typing import Sequence
import typing as ty
import functools
import operator
from types import TracebackType, UnionType
from enum import Enum
import builtins
from copy import copy
import json
import re
import inspect
from importlib import import_module
from inspect import isclass, isfunction
from pathlib import PurePath, Path
import logging
import attrs
from fileformats.core import from_mime, to_mime, DataType
import fileformats.field
import pydra.compose.base
import pydra.compose.python
import pydra.compose.workflow
from pydra.utils import get_fields
from pydra.utils.typing import optional_type, is_fileset_or_union
from pydra.engine.workflow import Workflow
from pydra.utils.typing import TypeParser, is_lazy
from pydra.engine.lazy import LazyField
from frametree.core.exceptions import (
    FrameTreeUsageError,
    FrametreeCannotSerializeDynamicDefinitionError,
)
from .packaging import pkg_versions, package_from_module
from .utils import add_exc_note
from frametree.core import PACKAGE_NAME


logger = logging.getLogger("frametree")


FRAMETREE_PIP = "git+ssh://git@github.com/australian-imaging-service/frametree.git"

HASH_CHUNK_SIZE = 2**20  # 1MB in calc. checksums to avoid mem. issues


@attrs.define
class _FallbackContext:
    """Used to specify that class resolution is permitted to fail within this context
    and return just a string (i.e. in build environments where the required modules
    aren't installed)
    """

    permit: bool = False

    def __enter__(self) -> None:
        self.permit = True

    def __exit__(
        self,
        exception_type: ty.Optional[ty.Type[BaseException]],
        exception_value: ty.Optional[BaseException],
        traceback: ty.Optional[TracebackType],
    ) -> None:
        self.permit = False


@attrs.define
class ClassResolver:
    """
    Parameters
    ----------
    base_class : type
        the target class to resolve the string representation to
    allow_none : bool
        whether None is a valid value, if True, None is returned if the string is None
    alternative_types : list[type]
        alternative types that are allowed to be resolved to
    package : str
        the package to resolve the class from if a partial path is given
    resolve_from_module : bool
        whether to resolve the class from the module if only the module name is given
    """

    base_class: ty.Optional[type] = None
    allow_none: bool = False
    alternative_types: ty.List[type] = attrs.field(factory=list)
    package: str = PACKAGE_NAME

    def __call__(self, class_str: str) -> type:
        """
        Resolves a class from a location string in the format "<module-name>:<class-name>"

        Parameters
        ----------
        class_str : str
            Module path and name of class joined by ':', e.g. main_pkg.sub_pkg:MyClass

        Returns
        -------
        type:
            The resolved class
        """
        if class_str is None and self.allow_none:
            return None
        # If only provided with name, attempt to treat it as a submodule/package of the package
        # and there is only one subclass of the base class in the module
        if isinstance(class_str, str) and ":" not in class_str and "/" not in class_str:
            try:
                mod = import_module(self.package + "." + class_str)
            except ModuleNotFoundError:
                pass
            else:
                mod_attrs = [getattr(mod, name) for name in dir(mod)]
                classes = [
                    a
                    for a in mod_attrs
                    if isclass(a) and issubclass(a, self.base_class)
                ]
                if not classes:
                    raise ValueError(
                        f"Did not find a class in module '{class_str}' that is a "
                        f"subclass of {self.base_class}"
                    )
                if len(classes) > 1:
                    superclasses = [
                        c for c in classes if all(issubclass(sc, c) for sc in classes)
                    ]
                    if len(superclasses) == 1:
                        return superclasses[0]
                    raise ValueError(
                        f"Found multiple classes in module '{class_str}' that are "
                        f"subclasses of {self.base_class}: {classes}"
                    )
                return classes[0]
        klass = self.fromstr(class_str, subpkg=True, pkg=self.package)
        base_class = optional_type(self.base_class)
        if (
            inspect.isclass(base_class)
            and inspect.isclass(klass)
            and issubclass(base_class, DataType)
            and not issubclass(klass, DataType)
        ):
            try:
                klass = fileformats.field.Field.from_primitive(klass)
            except TypeError:
                pass
        self._check_type(klass)
        return klass

    @classmethod
    def _get_subpkg(cls, klass: ty.Type[ty.Any]) -> ty.Optional[str]:
        try:
            return klass.SUBPACKAGE
        except AttributeError:
            return None

    @classmethod
    def fromstr(
        cls, class_str: str, subpkg: ty.Optional[str] = None, pkg: str = PACKAGE_NAME
    ) -> ty.Union[ty.Type[ty.Any], ty.Callable]:
        """Resolves a class/function from a string containing its module an its name
        separated by a ':'

        Parameters
        ----------
        class_str : str
            the string representation to resolve to a class or function
        subpkg : str, optional
            the sub-package that the class should belong to within the extension

        Returns
        -------
        type or callable
            the resolved class or function

        Raises
        ------
        ValueError
            raised if the string doesn't contain a ':'
        FrameTreeUsageError
            raised if the class wasn't found in the sub-package
        FrameTreeUsageError
            raised if a sub-package couldn't be found
        """
        if not isinstance(class_str, str):
            return class_str  # Assume that it is already resolved
        if "/" in class_str:  # Assume mime-type/like string
            return from_mime(class_str)
        if (
            "|" in class_str
        ):  # Assume union type; option 3: use functools.reduce with operator.or_
            union_args = tuple(
                cls.fromstr(t.strip(), subpkg=subpkg, pkg=pkg)
                for t in class_str.split("|")
            )
            return functools.reduce(operator.or_, union_args)
        if class_str.startswith("<") and class_str.endswith(">"):
            class_str = class_str[1:-1]
        try:
            module_path, class_name = class_str.split(":")
        except ValueError:
            try:
                return getattr(builtins, class_str)
            except AttributeError:
                module_path = None
                class_name = class_str
        assumed_common = False
        if not module_path:
            module_path = "common"  # default package
            assumed_common = True
        if "." in module_path:
            # Interpret as an absolute path not a relative path from an extension
            module_path = module_path.rstrip(
                "."
            )  # trailing '.' signifies top-level pkg
            subpkg = None
        module = None

        if subpkg:
            full_mod_path = ".".join((pkg, module_path))
            if isinstance(subpkg, str):
                full_mod_path += "." + subpkg
        else:
            full_mod_path = module_path
        try:
            module = import_module(full_mod_path)
        except ModuleNotFoundError:
            if cls.FALLBACK_TO_STR.permit:
                return class_str
            else:
                msg = (
                    f"Did not find module {full_mod_path}' when resolving {class_str} "
                    f"with subpkg={subpkg}.\n"
                )
                if assumed_common:
                    msg += (
                        "NB: No module path was provided, so the default 'common' "
                        "package was assumed. Please check it isn't meant to be a builtin "
                        "class or function instead"
                    )
                raise FrameTreeUsageError(msg)
        try:
            klass = getattr(module, class_name)
        except AttributeError:
            raise FrameTreeUsageError(
                f"Did not find '{class_str}' class/function in module '{module.__name__}'"
            )
        return klass

    @classmethod
    def tostr(cls, klass: ty.Type[ty.Any], strip_prefix: bool = True) -> str:
        """Records the location of a class so it can be loaded later using
        `ClassResolver`, in the format <module-name>:<class-name>

        Parameters
        ----------
        klass : Any
            the class/function to serialise to a string
        strip_prefix : bool
            whether to strip the SUBPACKAGE prefix from the module path when writing
            to file
        """
        if isinstance(klass, str):
            return klass
        if ty.get_origin(klass) is ty.Union or type(klass) is UnionType:
            if ty.get_origin(klass):
                args = ty.get_args(klass)
            else:
                args = klass.__args__
            return " | ".join(
                cls.tostr(t) if t is not type(None) else "None" for t in args
            )
        if not (isclass(klass) or isfunction(klass)):
            klass = type(klass)  # Get the class rather than the object
        if isclass(klass) and issubclass(klass, DataType):
            return to_mime(klass, official=False)

        module_name = get_module_name(klass)
        if module_name == "builtins":
            return klass.__name__
        if strip_prefix and cls._get_subpkg(klass):
            subpkg = cls._get_subpkg(klass)
            if match := re.match(r"frametree\.(\w+)\." + subpkg, module_name):
                module_name = match.group(
                    1
                )  # just use the name of the extension module
            elif "." not in module_name:
                module_name += "."  # To distinguish it from extension module name
        return module_name + ":" + klass.__name__

    def _check_type(self, klass: ty.Type[ty.Any]) -> None:
        if self.FALLBACK_TO_STR.permit and isinstance(klass, str):
            return
        if self.base_class:
            if isfunction(klass):
                if ty.Callable in self.alternative_types:
                    return  # ok
                else:
                    raise ValueError(
                        f"Found callable {klass}, but Callable isn't in alternative_types"
                    )
            if klass in self.alternative_types:
                return  # ok
            # TypeParser handles unions and other exotic base classes Python < 3.10
            if not (
                TypeParser.is_subclass(klass, self.base_class)
                or issubclass(klass, self.base_class)
            ):
                raise ValueError(
                    f"Found {klass}, which is not a subclass of {self.base_class}"
                )

    FALLBACK_TO_STR = _FallbackContext()


def asdict(
    obj: ty.Any,
    omit: ty.Iterable[str] = (),
    required_modules: ty.Optional[ty.Set[str]] = None,
) -> ty.Dict[str, ty.Any]:
    """Serialises an object of a class defined with attrs to a dictionary

    Parameters
    ----------
    obj
        The FrameTree object to asdict. Must be defined using the attrs
        decorator
    omit: Iterable[str]
        the names of attributes to omit from the dictionary
    required_modules: set[str], optional
        modules required to reload the serialised object into memory

    Returns
    -------
    dict
        the serialised object
    """

    def filter(atr: attrs.Attribute[ty.Any], value: ty.Any) -> bool:
        return (
            atr.init and atr.metadata.get("asdict", True) and value is not attrs.NOTHING
        )

    if required_modules is None:
        required_modules = set()
        include_versions = True  # Assume top-level dictionary so need to include
    else:
        include_versions = False

    def serialise_class(klass: ty.Type[ty.Any]) -> str:
        required_modules.add(get_module_name(klass))
        return "<" + ClassResolver.tostr(klass, strip_prefix=False) + ">"

    def value_asdict(value: ty.Any) -> ty.Dict[str, ty.Any]:
        if is_fileset_or_union(value):
            value = to_mime(value, official=False)
        elif isclass(value):
            value = serialise_class(value)
        elif hasattr(value, "asdict"):
            value = value.asdict(required_modules=required_modules)
        elif attrs.has(value):  # is class with attrs
            value_class = serialise_class(type(value))
            value = attrs.asdict(
                value,
                recurse=False,
                filter=filter,
                value_serializer=lambda i, f, v: value_asdict(v),
            )
            _replace_hidden(value)
            value["class"] = value_class
        elif isinstance(value, Enum):
            value = serialise_class(type(value)) + "[" + str(value) + "]"
        elif isinstance(value, PurePath):
            value = "file://" + str(value.resolve())
        elif isinstance(value, (tuple, list, set, frozenset)):
            value = [value_asdict(x) for x in value]
        elif isinstance(value, dict):
            value = {value_asdict(k): value_asdict(v) for k, v in value.items()}
        elif is_dataclass(value):
            value = [
                value_asdict(getattr(value, f.name)) for f in dataclass_fields(value)
            ]
        return value

    dct = attrs.asdict(
        obj,
        recurse=False,
        filter=lambda a, v: filter(a, v) and a.name not in omit,
        value_serializer=lambda i, f, v: value_asdict(v),
    )

    _replace_hidden(dct)

    dct["class"] = serialise_class(type(obj))
    if include_versions:
        dct["pkg_versions"] = pkg_versions(required_modules)

    return dct


def _replace_hidden(dct: ty.Dict[str, ty.Any]) -> None:
    "Replace hidden attributes (those starting with '_') with non-hidden"
    for key in list(dct):
        if key.startswith("_"):
            dct[key[1:]] = dct.pop(key)


def fromdict(dct: ty.Dict[str, ty.Any], **kwargs: ty.Any) -> object:
    """Unserialise an object from a dict created by the `asdict` method

    Parameters
    ----------
    dct : dict
        A dictionary containing a serialsed FrameTree object such as a data store
        or dataset definition
    omit: Iterable[str]
        key names to ignore when unserialising
    **kwargs : dict[str, Any]
        Additional initialisation arguments for the object when it is reinitialised.
        Overrides those stored"""
    # try:
    #     frametree_version = dct["pkg_versions"]["frametree"]
    # except (TypeError, KeyError):
    #     pass
    #     else:
    #         if (packaging.version.parse(frametree_version)
    #               < packaging.version.parse(MIN_SERIAL_VERSION)):
    #             raise FrameTreeVersionError(
    #                 f"Serialised version ('{frametree_version}' is too old to be "
    #                 f"read by this version of frametree ('{__version__}'), the minimum "
    #                 f"version is {MIN_SERIAL_VERSION}")

    def field_filter(klass: ty.Type[ty.Any], field_name: str) -> bool:
        if attrs.has(klass):
            return field_name in (f.name for f in attrs.fields(klass))
        else:
            return field_name != "class"

    def fromdict(
        value: ty.Union[
            ty.Dict[str, ty.Any],
            str,
            ty.Sequence[ty.Dict[str, ty.Any]],
        ],
    ) -> ty.Any:
        resolved_value: ty.Any = value
        if isinstance(value, dict):
            if "class" in value:
                klass = ClassResolver()(value["class"])
                if hasattr(klass, "fromdict"):
                    return klass.fromdict(value)
            resolved_value = {fromdict(k): fromdict(v) for k, v in value.items()}
            if "class" in resolved_value:
                resolved_value = klass(
                    **{
                        k: v
                        for k, v in resolved_value.items()
                        if field_filter(klass, k)
                    }
                )
        elif isinstance(value, str):
            if match := re.match(r"<(.*)>$", value):  # Class location
                resolved_value = ClassResolver()(match.group(1))
            elif match := re.match(
                r"<(.*)>\[(.*)\]$", value
            ):  # Enum or classified format
                resolved_value = ClassResolver()(match.group(1))[match.group(2)]  # type: ignore[index]
            elif match := re.match(r"file://(.*)", value):
                resolved_value = Path(match.group(1))
        elif isinstance(value, Sequence):
            resolved_value = [fromdict(x) for x in value]
        return resolved_value

    klass = ClassResolver()(dct["class"])

    kwargs.update(
        {
            k: fromdict(v)
            for k, v in dct.items()
            if field_filter(klass, k) and k not in kwargs
        }
    )

    return klass(**kwargs)


extract_import_re = re.compile(r"\s*(?:from|import)\s+([\w\.]+)")

NOTHING_STR = "__PIPELINE_INPUT__"


def pydra_asdict(
    obj: pydra.compose.base.Task,
    required_modules: ty.Set[str],
    workflow: ty.Optional[Workflow] = None,
) -> ty.Dict[str, ty.Any]:
    """Converts a Pydra Task/Workflow into a dictionary that can be serialised

    Parameters
    ----------
    obj : pydra.compose.base.Task
        the Pydra object to convert to a dictionary
    required_modules : set[str]
        a set of modules that are required to load the pydra object back
        out from disk and run it
    workflow : pydra.Workflow, optional
        the containing workflow that the object to serialised is part of

    Returns
    -------
    dict
        the dictionary containing the contents of the Pydra object
    """
    dct = {
        "class": "<" + ClassResolver.tostr(obj, strip_prefix=False) + ">",
    }
    if isinstance(obj, Workflow):
        dct["nodes"] = [
            pydra_asdict(n, required_modules=required_modules, workflow=obj)
            for n in obj.nodes
        ]
        dct["outputs"] = outputs = {}
        for outpt_name, lf in obj._connections:
            outputs[outpt_name] = {"task": lf.name, "field": lf.field}
    else:
        if isinstance(obj, (pydra.compose.python.Task, pydra.compose.workflow.Task)):
            klass = type(obj)
            func = (
                obj.function
                if isinstance(obj, pydra.compose.python.Task)
                else obj.constructor
            )
            if klass.__module__ == "types":
                mod_name = func.__module__
            else:
                mod_name = klass.__module__
            dct["class"] = "<" + mod_name + ":" + klass.__name__ + ">"
            required_modules.add(mod_name)
            # inspect source for any import lines (should be present in function
            # not module)
            for line in inspect.getsourcelines(func)[0]:
                if match := extract_import_re.match(line):
                    required_modules.add(match.group(1))
            # TODO: check source for references to external modules that aren't
            #       imported within function
        else:
            pkg = package_from_module(type(obj).__module__)
            dct["package"] = pkg.key
            dct["version"] = pkg.version
        if hasattr(obj, "container"):
            dct["container"] = {"type": obj.container, "image": obj.image}
    dct["inputs"] = inputs = {}
    for inpt in get_fields(obj):
        if inpt.name.startswith("_"):
            continue
        inpt_value = getattr(obj, inpt.name)
        if (
            obj._task_type() == "python"
            and inpt.name == "function"
            and inpt_value is inpt.default
        ):
            # Don't include the function in the serialised object
            continue
        if (
            obj._task_type() == "workflow"
            and inpt.name == "constructor"
            and inpt_value is inpt.default
        ):
            # Don't include the constructor in the serialised object
            continue
        if is_lazy(inpt_value):
            inputs[inpt.name] = {"field": inpt_value.field}
            # If the lazy field comes from the workflow lazy in, we omit
            # the "task" item
            if workflow is None or inpt_value.name != workflow.name:
                inputs[inpt.name]["task"] = inpt_value.name
        elif inpt_value == attrs.NOTHING:
            inputs[inpt.name] = NOTHING_STR
        else:
            inputs[inpt.name] = inpt_value
    return dct


def lazy_field_fromdict(dct: ty.Dict[ty.Any, ty.Any], workflow: Workflow) -> LazyField:
    """Unserialises a LazyField object from a dictionary"""
    if "task" in dct:
        inpt_task = getattr(workflow, dct["task"])
        lf = getattr(inpt_task.lzout, dct["field"])
    else:
        lf = getattr(workflow.lzin, dct["field"])
    return lf


def pydra_fromdict(
    dct: ty.Dict[ty.Any, ty.Any],
    workflow: ty.Optional[Workflow] = None,
    **kwargs: ty.Any,
) -> pydra.compose.base.Task:
    """Recreates a Pydra Task/Workflow from a dictionary object created by
    `pydra_asdict`

    Parameters
    ----------
    dct : dict
        dictionary representations of the object to recreate
    name : str
        name to give the object
    workflow : pydra.Workflow, optional
        the containing workflow that the object to recreate is connected to
    **kwargs
        additional keyword arguments passed to the pydra Object init method

    Returns
    -------
    pydra.compose.base.Task
        the recreated Pydra object
    """
    klass = ClassResolver()(dct["class"])
    # Resolve lazy-field references to workflow fields
    inputs = {}
    for inpt_name, inpt_val in dct["inputs"].items():
        if inpt_val == NOTHING_STR:
            continue
        # Check for 'field' key in a dictionary val and convert to a
        # LazyField object
        if isinstance(inpt_val, dict) and "field" in inpt_val:
            inpt_val = lazy_field_fromdict(inpt_val, workflow=workflow)
        inputs[inpt_name] = inpt_val
    kwargs.update((k, v) for k, v in inputs.items() if k not in kwargs)
    if klass is Workflow:
        obj = Workflow(name=dct["name"], input_spec=list(dct["inputs"]), **kwargs)
        for node_dict in dct["nodes"]:
            obj.add(pydra_fromdict(node_dict, workflow=obj))
        obj.set_output(
            [
                (n, lazy_field_fromdict(f, workflow=obj))
                for n, f in dct["outputs"].items()
            ]
        )
    else:
        obj = klass(**kwargs)
    return obj


@attrs.define
class ObjectConverter:

    klass: type
    allow_none: bool = False
    default_if_none: ty.Any = None
    accept_metadata: bool = False
    package: str = PACKAGE_NAME

    def __call__(self, value: ty.Any) -> ty.Any:
        return self._create_object(value)

    def _create_object(self, value: ty.Any, **kwargs: ty.Any) -> ty.Any:
        if value is None:
            if kwargs:
                value = {}
            elif self.allow_none:
                if callable(self.default_if_none):
                    default = self.default_if_none()
                else:
                    default = self.default_if_none
                return default
            else:
                raise ValueError(
                    f"None values not accepted in automatic conversion to {self.klass}"
                )
        if isinstance(value, dict):
            if self.accept_metadata:
                klass_attrs = set(attrs.fields_dict(self.klass))
                value_kwargs = {k: v for k, v in value.items() if k in klass_attrs}
                value_kwargs["metadata"] = {
                    k: v for k, v in value.items() if k not in klass_attrs
                }
            else:
                value_kwargs = value
            value_kwargs.update(kwargs)
            try:
                obj = self.klass(**value_kwargs)
            except TypeError as e:
                field_names = [f.name for f in attrs.fields(self.klass)]
                msg = f"when creating {self.klass} from {value_kwargs}, expected {field_names}"
                add_exc_note(e, msg)
                raise
        elif isinstance(value, (list, tuple)):
            obj = self.klass(*value, **kwargs)
        elif isinstance(value, self.klass):
            obj = copy(value)
            for k, v in kwargs.items():
                setattr(obj, k, v)
        elif isinstance(value, (str, int, float, bool)):
            # If there are kwargs that are in the first N positions of the
            # argument list, add them in as positional arguments first and then
            # append the value to the end of the args list
            args = []
            kgs = copy(kwargs)
            for field_name in attrs.fields_dict(self.klass):
                try:
                    args.append(kgs.pop(field_name))
                except KeyError:
                    break
            args.append(value)
            obj = self.klass(*args, **kgs)
        else:
            raise ValueError(f"Cannot convert {value} into {self.klass}")
        return obj


@attrs.define
class ObjectListConverter(ObjectConverter):
    def __call__(self, value: ty.Any) -> ty.List[ty.Any]:
        converted: ty.List[ty.Any] = []
        if value is None:
            if self.allow_none:
                return converted
            else:
                raise ValueError("Value cannot be None")
        if isinstance(value, dict):
            for name, item in value.items():
                converted.append(self._create_object(item, name=name))
        else:
            for item in value:
                converted.append(self._create_object(item))
        return converted

    @classmethod
    def asdict(cls, objs: ty.List[ty.Any], **kwargs: ty.Any) -> ty.Dict[str, ty.Any]:
        dct = {}
        for obj in objs:
            obj_dict = attrs.asdict(obj, **kwargs)
            dct[obj_dict.pop("name")] = obj_dict
        return dct

    @classmethod
    def aslist(cls, objs: ty.List[ty.Any], **kwargs: ty.Any) -> ty.List[ty.Any]:
        return [attrs.asdict(obj, **kwargs) for obj in objs]


def parse_value(value: ty.Any) -> ty.Any:
    """Parses values from string representations"""
    try:
        value = json.loads(
            value
        )  # FIXME: Is this value replace really necessary, need to investigate where it is used again
    except (TypeError, json.decoder.JSONDecodeError):
        pass
    return value


def get_module_name(klass: type) -> str:
    """Gets the module in which the klass was defined, taking into account dynamically
    created Pydra Task classes"""
    if klass.__module__ == "types":
        try:
            executor_name = klass._executor_name
        except AttributeError:
            pass
        else:
            executor = get_fields(klass)[executor_name].default
            try:
                module = executor.__module__
            except AttributeError:
                pass
            else:
                if module != "types":
                    return module
        raise FrametreeCannotSerializeDynamicDefinitionError(
            f"Cannot serialise {klass} as it is a dynamically created class"
        )
    return klass.__module__

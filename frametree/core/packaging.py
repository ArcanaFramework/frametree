from __future__ import annotations
import json
import typing as ty
import importlib.metadata
import pkgutil
from importlib import import_module
from inspect import isclass
from pathlib import Path
from collections.abc import Iterable
from pydra.utils.general import STDLIB_MODULES
from frametree.core.exceptions import FrameTreeUsageError
from frametree.core import __version__, PACKAGE_NAME


def submodules(
    package: ty.Any, subpkg: str | None = None
) -> ty.Generator[ty.Any, None, None]:
    """Iterates all modules within the given package"""
    for mod_info in pkgutil.iter_modules(
        package.__path__, prefix=package.__package__ + "."
    ):
        if mod_info.name == "core":
            continue
        if subpkg is not None:
            try:
                yield import_module(mod_info.name + "." + subpkg)
            except ImportError:
                continue
        else:
            yield import_module(mod_info.name)


def list_subclasses(
    package: ty.Any, base_class: type, subpkg: str | None = None
) -> list[type]:
    """List all available subclasses of a base class in modules within the given package"""
    subclasses: list[type] = []
    for module in submodules(package, subpkg=subpkg):
        for obj_name in dir(module):
            obj = getattr(module, obj_name)
            if isclass(obj) and issubclass(obj, base_class) and obj is not base_class:
                subclasses.append(obj)
    return subclasses


def package_from_module(
    module: str | ty.Any | Iterable[str | ty.Any],
) -> importlib.metadata.Distribution | tuple[importlib.metadata.Distribution, ...]:
    """Resolves the installed package (e.g. from PyPI) that provides the given module."""
    module_paths: set[str] = set()
    if isinstance(module, Iterable) and not isinstance(module, str):
        modules = module
        as_tuple = True
    else:
        modules = [module]
        as_tuple = False
    for module in modules:
        try:
            module_path = module.__name__
        except AttributeError:
            module_path = module
        module_paths.add(module_path.replace(".", "/"))
    packages: set[importlib.metadata.Distribution] = set()
    for dist in importlib.metadata.distributions():
        if editable_dir := get_editable_dir(dist):

            def is_in_pkg(module_path: str) -> bool:
                pth = editable_dir.joinpath(module_path)
                return pth.with_suffix(".py").exists() or (pth / "__init__.py").exists()

        else:
            installed_paths = installed_module_paths(dist)

            def is_in_pkg(module_path: str) -> bool:
                return module_path in installed_paths

        if in_pkg := set(m for m in module_paths if is_in_pkg(m)):
            packages.add(dist)
            module_paths -= in_pkg
            if not module_paths:
                break
    if module_paths:
        paths_str = "', '".join(str(p) for p in module_paths)
        raise FrameTreeUsageError(f"Did not find package for {paths_str}")
    return tuple(packages) if as_tuple else next(iter(packages))


def get_editable_dir(dist: importlib.metadata.Distribution) -> Path | None:
    """Returns the path to the editable dir to a package if it exists"""
    if not hasattr(dist, "locate_file"):
        return None
    try:
        dist_info_dir = dist.locate_file("")
        direct_url_path = Path(dist_info_dir) / "direct_url.json"
        if not direct_url_path.exists():
            return None
        with open(direct_url_path) as f:
            url_spec = json.load(f)
        url: str = url_spec["url"]
        if "dir_info" not in url_spec or not url_spec["dir_info"].get("editable"):
            return None
        assert url.startswith("file://")
        return Path(url[len("file://") :])
    except Exception:
        return None


def installed_module_paths(dist: importlib.metadata.Distribution) -> set[str]:
    """Returns the list of modules that are part of an installed package"""
    try:
        paths = importlib.metadata.files(dist.metadata["Name"])
    except (importlib.metadata.PackageNotFoundError, KeyError, AttributeError):
        paths = []
    if paths is None:
        paths = []
    result: set[str] = set(
        str(p.parent) if p.name == "__init__.py" else str(p.with_suffix(""))
        for p in paths
        if p.suffix == ".py"
    )
    return result


def pkg_versions(modules: Iterable[str]) -> dict[str, str]:
    nonstd = [m for m in modules if m.split(".")[0] not in STDLIB_MODULES]
    versions: dict[str, str] = {
        d.metadata["Name"]: d.version for d in package_from_module(nonstd)
    }
    versions[PACKAGE_NAME] = __version__
    return versions

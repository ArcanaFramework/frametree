import warnings
from .axes.samples import Samples
from .axes.clinical import Clinical
from .file_system import FileSystem


warnings.warn(
    "Importing from frametree.common is deprecated, import from frametree.axes or frametree.file_system instead",
    DeprecationWarning,
)

__all__ = ["Samples", "Clinical", "FileSystem"]

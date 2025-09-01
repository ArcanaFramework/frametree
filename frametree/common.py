import warnings
from .axes.samples import Samples
from .axes.medimage import MedImage as MedImage
from .file_system import FileSystem


warnings.warn(
    "Importing from frametree.common is deprecated, import FileSystem store from frametree.file_system instead, and the "
    "frametree.common.MedImage axes has been renamed to frametree.axes.medimage.MedImage",
    DeprecationWarning,
)

__all__ = ["Samples", "MedImage", "FileSystem"]

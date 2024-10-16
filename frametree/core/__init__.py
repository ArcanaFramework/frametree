from ._version import __version__  # noqa: F401

PACKAGE_NAME = "frametree"
CODE_URL = f"https://github.com/ArcanaFramework/{PACKAGE_NAME}"

__authors__ = [("Thomas G. Close", "tom.g.close@gmail.com")]

from .frameset import FrameSet  # noqa: E402

__all__ = ["FrameSet"]

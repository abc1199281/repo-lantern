# Lantern CLI - Core Package
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("repo-lantern")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

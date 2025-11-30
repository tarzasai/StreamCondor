"""streamcondor package root

Keep this file lightweight to avoid importing submodules at package import
time. Importing `streamcondor.main` during package import can trigger a
RuntimeWarning when the module is executed with `python -m streamcondor.main`.
Provide a small lazy wrapper that imports the real `main` only when called.
"""

from typing import Callable

# Package version (single source of truth for runtime version display).
# If the project is built with setuptools_scm, it will write `src/streamcondor/_version.py`.
# Otherwise fall back to a default value for local development.
try:
  # Attempt to import the generated version module written by setuptools_scm
  from ._version import version as __version__  # type: ignore
except Exception:
  __version__ = "1.0.0"

def main() -> None:
  """Lazy entry point that imports the real `main` only when invoked."""
  from .main import main as _real_main
  return _real_main()

__all__ = ["main", "__version__"]

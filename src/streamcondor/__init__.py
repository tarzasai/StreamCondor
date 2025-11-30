"""streamcondor package root

Keep this file lightweight to avoid importing submodules at package import
time. Importing `streamcondor.main` during package import can trigger a
RuntimeWarning when the module is executed with `python -m streamcondor.main`.
Provide a small lazy wrapper that imports the real `main` only when called.
"""

from typing import Callable

def main() -> None:
	"""Lazy entry point that imports the real `main` only when invoked."""
	from .main import main as _real_main
	return _real_main()

__all__ = ["main"]

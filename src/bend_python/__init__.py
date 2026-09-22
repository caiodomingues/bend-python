"""Compile Bend functions once and call them from Python through a native library."""

from __future__ import annotations

import os
from collections.abc import Mapping

from .compiler import BEND_VERSION, build
from .errors import BendError, BuildError, ClosedError, CompatibilityError, NativeError
from .module import Module, NativeFunction, load
from .types import F32, U32, Bool, Function, Scalar

__version__ = "0.1.0"
__all__ = [
    "BEND_VERSION",
    "BendError",
    "Bool",
    "BuildError",
    "ClosedError",
    "CompatibilityError",
    "F32",
    "Function",
    "Module",
    "NativeError",
    "NativeFunction",
    "Scalar",
    "U32",
    "__version__",
    "build",
    "compile_module",
    "load",
]


def compile_module(
    source: str | os.PathLike[str],
    *,
    exports: Mapping[str, Function],
    threads: int = 1,
    build_dir: str | os.PathLike[str] | None = None,
    bend: str | os.PathLike[str] | None = None,
    cc: str | os.PathLike[str] | None = None,
    timeout: float = 120,
) -> Module:
    """Build a native artifact and load it with its own runtime."""
    artifact = build(
        source, exports=exports, build_dir=build_dir, bend=bend, cc=cc, timeout=timeout
    )
    return load(artifact, threads=threads)

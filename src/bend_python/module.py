"""Load native artifacts with isolated runtime state and explicit ownership."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
import threading
import weakref
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType, TracebackType

from .compiler import ABI_VERSION, BEND_VERSION
from .errors import ClosedError, CompatibilityError, NativeError
from .types import Function, Scalar


def _dispose(lib: ctypes.CDLL, directory: tempfile.TemporaryDirectory[str], pid: int) -> None:
    if os.getpid() == pid:
        lib.bendpy_close()
        directory.cleanup()


class _Runtime:
    def __init__(self, library: Path, abi: str, threads: int) -> None:
        self.pid = os.getpid()
        self.lock = threading.Lock()
        self.closed = False
        self.threads = threads
        directory = tempfile.TemporaryDirectory(prefix="bend-python-")
        try:
            private_library = Path(directory.name) / "module.so"
            shutil.copyfile(library, private_library)
            self.lib = ctypes.CDLL(str(private_library), mode=os.RTLD_LOCAL)
            self.lib.bendpy_abi.argtypes = []
            self.lib.bendpy_abi.restype = ctypes.c_char_p
            self.lib.bendpy_thread_limit.argtypes = []
            self.lib.bendpy_thread_limit.restype = ctypes.c_uint32
            self.lib.bendpy_call.argtypes = [
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            self.lib.bendpy_call.restype = ctypes.c_int
            self.lib.bendpy_close.argtypes = []
            self.lib.bendpy_close.restype = ctypes.c_int
            if self.lib.bendpy_abi() != abi.encode("ascii"):
                raise CompatibilityError(
                    "library and manifest describe different export signatures"
                )
            limit = int(self.lib.bendpy_thread_limit())
            if threads > limit:
                raise ValueError(f"threads must be between 1 and {limit}")
        except (OSError, AttributeError) as exc:
            directory.cleanup()
            raise CompatibilityError(f"cannot load native Bend library: {exc}") from exc
        except BaseException:
            directory.cleanup()
            raise
        self._finalizer = weakref.finalize(self, _dispose, self.lib, directory, self.pid)

    def check_process(self) -> None:
        if os.getpid() != self.pid:
            raise NativeError(
                "a loaded Bend module cannot be used after fork; load it in the child"
            )

    def call(self, index: int, words: list[int]) -> int:
        self.check_process()
        arguments = (ctypes.c_uint32 * len(words))(*words)
        result = ctypes.c_uint32()
        with self.lock:
            if self.closed:
                raise ClosedError("the Bend module is closed")
            status = self.lib.bendpy_call(
                index, arguments, len(words), self.threads, ctypes.byref(result)
            )
            if status:
                raise NativeError(f"native call failed with boundary status {status}")
        return int(result.value)

    def close(self) -> None:
        self.check_process()
        with self.lock:
            if not self.closed:
                self.closed = True
                self._finalizer()


class NativeFunction:
    """A scalar function retaining its module's native runtime."""

    def __init__(self, name: str, index: int, signature: Function, runtime: _Runtime) -> None:
        self.__name__ = name
        self.signature = signature
        self._index = index
        self._runtime = runtime

    def __call__(self, *args: object) -> int | float | bool:
        if len(args) != len(self.signature.args):
            raise TypeError(
                f"{self.__name__} expects {len(self.signature.args)} arguments; got {len(args)}"
            )
        words = [kind.encode(value) for kind, value in zip(self.signature.args, args, strict=True)]
        return self.signature.returns.decode(self._runtime.call(self._index, words))


class Module:
    """An independently loaded Bend runtime; use as a context manager or close it."""

    def __init__(
        self, artifact: Path, runtime: _Runtime, signatures: Mapping[str, Function]
    ) -> None:
        self.artifact = artifact
        self._runtime = runtime
        self.functions: Mapping[str, NativeFunction] = MappingProxyType(
            {
                name: NativeFunction(name, index, signature, runtime)
                for index, (name, signature) in enumerate(signatures.items())
            }
        )

    @property
    def threads(self) -> int:
        return self._runtime.threads

    @property
    def closed(self) -> bool:
        return self._runtime.closed

    def __getattr__(self, name: str) -> NativeFunction:
        functions = self.__dict__.get("functions", {})
        try:
            function: NativeFunction = functions[name]
            return function
        except KeyError:
            raise AttributeError(f"no exported Bend function {name!r}") from None

    def __getitem__(self, name: str) -> NativeFunction:
        return self.functions[name]

    def close(self) -> None:
        """Wait for the active call, stop workers, and release the runtime's mappings."""
        self._runtime.close()

    def __enter__(self) -> Module:
        self._runtime.check_process()
        if self.closed:
            raise ClosedError("the Bend module is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def load(artifact: str | os.PathLike[str], *, threads: int = 1) -> Module:
    """Load a trusted build manifest without requiring Bend or clang at runtime.

    Loading the same artifact twice creates independent runtimes. Calls on one
    runtime are serialized; ctypes releases the GIL during the native call.
    """
    if sys.platform != "linux":
        raise CompatibilityError("native loading currently requires Linux; on Windows use WSL2")
    if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
        raise ValueError("threads must be a positive integer")
    manifest = Path(artifact).resolve(strict=True)
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data["abi"] != ABI_VERSION or data["bend"] != BEND_VERSION:
            raise CompatibilityError("unsupported bend-python artifact ABI or Bend version")
        if data["platform"] != sys.platform or data["machine"] != platform.machine():
            raise CompatibilityError("artifact was built for a different operating system or CPU")
        library_name = data["library"]
        if not isinstance(library_name, str) or Path(library_name).name != library_name:
            raise CompatibilityError("manifest library must be a filename")
        library = manifest.parent / library_name
        if hashlib.sha256(library.read_bytes()).hexdigest() != data["sha256"]:
            raise CompatibilityError("library checksum does not match its manifest")
        signatures = {
            item["export"]: Function(
                [Scalar(arg) for arg in item["args"]], Scalar(item["returns"]), name=item["name"]
            )
            for item in data["exports"]
        }
        from ._generate import validate_exports

        validate_exports(signatures)
        contract = {key: data[key] for key in ("abi", "bend", "exports")}
        abi = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
        if abi != data["abi_hash"] or len(signatures) != len(data["exports"]):
            raise CompatibilityError("manifest export signatures were modified")
    except (KeyError, ValueError, TypeError, OSError) as exc:
        raise CompatibilityError(f"invalid Bend artifact: {exc}") from exc
    return Module(manifest, _Runtime(library, abi, threads), signatures)

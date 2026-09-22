"""Compile explicit Bend exports into a reusable native artifact."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Mapping
from pathlib import Path

from ._generate import validate_exports, wrapper
from ._runtime_patch import adapt_runtime
from .errors import BuildError, CompatibilityError
from .types import Function

BEND_VERSION = "2.0.25"
ABI_VERSION = 1


def _run(command: list[str], *, timeout: float) -> str:
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env={**os.environ, "BEND_NO_TELEMETRY": "1"},
            check=False,
        )
    except FileNotFoundError as exc:
        raise BuildError(f"tool not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise BuildError(
            f"{Path(command[0]).name} exceeded the {timeout:g}s build timeout"
        ) from exc
    except OSError as exc:
        raise BuildError(f"could not execute {command[0]}: {exc}") from exc
    if result.returncode:
        raise BuildError(f"{Path(command[0]).name} exited {result.returncode}:\n{result.stdout}")
    return result.stdout


def build(
    source: str | os.PathLike[str],
    *,
    exports: Mapping[str, Function],
    build_dir: str | os.PathLike[str] | None = None,
    bend: str | os.PathLike[str] | None = None,
    cc: str | os.PathLike[str] | None = None,
    timeout: float = 120,
) -> Path:
    """Build a manifest and shared library; return the manifest path.

    The installed Bend compiler checks the generated wrapper and all reachable
    imports. Only trusted source should be compiled or loaded. No toolchain is
    downloaded by this function.
    """
    if sys.platform != "linux":
        raise CompatibilityError("native builds currently require Linux; on Windows use WSL2")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    source_path = Path(source).resolve(strict=True)
    if not source_path.is_file() or source_path.suffix != ".bend":
        raise ValueError("source must be a .bend file")
    signatures = validate_exports(exports)
    generated = wrapper(source_path, signatures)
    bend_exe = os.fspath(bend) if bend is not None else os.environ.get("BENDPY_BEND", "bend")
    cc_exe = os.fspath(cc) if cc is not None else os.environ.get("BENDPY_CC", "clang")
    version = _run([bend_exe, "version"], timeout=timeout).strip()
    if version != f"bend {BEND_VERSION}":
        raise CompatibilityError(f"expected bend {BEND_VERSION}; found {version!r}")
    compiler_version = _run([cc_exe, "--version"], timeout=timeout)
    if "clang version" not in compiler_version:
        raise CompatibilityError("Bend's C output requires clang")
    if build_dir is None:
        build_path = source_path.parent / ".bend-python" / f"{source_path.stem}-{uuid.uuid4().hex}"
    else:
        build_path = Path(build_dir).resolve()
    build_path.mkdir(parents=True, exist_ok=True)
    descriptions = [
        {
            "export": name,
            "name": signature.name or name,
            "args": [arg.value for arg in signature.args],
            "returns": signature.returns.value,
        }
        for name, signature in signatures.items()
    ]
    contract = {"abi": ABI_VERSION, "bend": BEND_VERSION, "exports": descriptions}
    abi = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    resources = Path(__file__).with_name("native")
    arities = ", ".join(str(len(signature.args)) for signature in signatures.values())
    config = (
        f'#define BP_ABI "{abi}"\n#define BP_EXPORTS {len(signatures)}\n'
        f"static const uint32_t bp_argc[BP_EXPORTS] = {{{arities}}};\n"
    )
    with tempfile.TemporaryDirectory(prefix="compile-", dir=build_path) as temporary:
        staging = Path(temporary)
        entry = staging / "main.bend"
        entry.write_text(generated, encoding="utf-8")
        (staging / "bridge.c").write_text(
            config + (resources / "bridge.c").read_text(encoding="utf-8"), encoding="utf-8"
        )
        shutil.copyfile(resources / "bridge.js", staging / "bridge.js")
        emitted = staging / "module.c"
        log = _run([bend_exe, str(entry), "-o", str(emitted)], timeout=timeout)
        emitted.write_text(adapt_runtime(emitted.read_text(encoding="utf-8")), encoding="utf-8")
        library = staging / "module.so"
        log += _run(
            [
                cc_exe,
                "-std=c11",
                "-O2",
                "-shared",
                "-fPIC",
                "-fvisibility=hidden",
                "-Dmain=bendpy_unused_cli_main",
                str(emitted),
                "-lpthread",
                "-lm",
                "-o",
                str(library),
            ],
            timeout=timeout,
        )
        library_name = f"module-{uuid.uuid4().hex}.so"
        metadata = {
            **contract,
            "abi_hash": abi,
            "library": library_name,
            "sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
            "platform": sys.platform,
            "machine": platform.machine(),
            "source": source_path.name,
        }
        shutil.copyfile(library, build_path / library_name)
        (build_path / "build.log").write_text(log, encoding="utf-8")
        (build_path / "wrapper.bend").write_text(generated, encoding="utf-8")
        (staging / "module.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(staging / "module.json", build_path / "module.json")
    return build_path / "module.json"

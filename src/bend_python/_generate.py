"""Generate a type-checked Bend adapter; leave user modules untouched."""

from __future__ import annotations

import keyword
import re
from collections.abc import Mapping
from pathlib import Path

from .types import F32, Bool, Function

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
_RESERVED = {"close", "closed", "functions", "threads", "artifact", "metadata"}


def validate_exports(exports: Mapping[str, Function]) -> dict[str, Function]:
    if not exports:
        raise ValueError("at least one export is required")
    if len(exports) > 256:
        raise ValueError("at most 256 exports are supported")
    result = dict(exports)
    for name, signature in result.items():
        if (
            not isinstance(name, str)
            or not name.isascii()
            or not name.isidentifier()
            or keyword.iskeyword(name)
            or name.startswith("_")
            or name in _RESERVED
        ):
            raise ValueError(f"invalid or reserved Python export name: {name!r}")
        if not isinstance(signature, Function):
            raise TypeError(f"{name}: expected Function signature")
        if not isinstance(signature.name or name, str) or not _NAME.fullmatch(
            signature.name or name
        ):
            raise ValueError(f"invalid Bend function name: {signature.name!r}")
    return result


def wrapper(source: Path, exports: Mapping[str, Function]) -> str:
    path = source.as_posix()
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", path):
        raise ValueError(
            "Bend import paths currently require ASCII letters, digits, _, -, /, and ."
        )
    lines = [
        "import Base",
        f"import {path} as User",
        "",
        "def BendPy.select() -> IO(U32):",
        '  import "./bridge.c"',
        '  import "./bridge.js"',
        "",
        "def BendPy.arg_u32(index: U32) -> IO(U32):",
        '  import "./bridge.c"',
        '  import "./bridge.js"',
        "",
        "def BendPy.arg_f32(index: U32) -> IO(F32):",
        '  import "./bridge.c"',
        '  import "./bridge.js"',
        "",
        "def BendPy.ret(value: U32) -> IO(Unit):",
        '  import "./bridge.c"',
        '  import "./bridge.js"',
        "",
        "def BendPy.bool(value: U32) -> Bool:",
        "  match value:",
        "    case 0:",
        "      False{}",
        "    case _:",
        "      True{}",
        "",
    ]
    for index, (name, signature) in enumerate(exports.items()):
        lines.extend([f"def BendPy.fn{index}() -> IO(Unit):", "  do IO<Unit>:"])
        arguments = []
        for arg_index, arg in enumerate(signature.args):
            variable = f"arg{arg_index}"
            if arg is F32:
                lines.append(f"    {variable} : F32 <- BendPy.arg_f32({arg_index})")
            else:
                lines.append(f"    {variable} : U32 <- BendPy.arg_u32({arg_index})")
            arguments.append(f"BendPy.bool({variable})" if arg is Bool else variable)
        call = f"User.{signature.name or name}({', '.join(arguments)})"
        lines.append(f"    result : {signature.returns.value} = {call}")
        output = "result"
        if signature.returns is F32:
            output = "F32.bits(result)"
        elif signature.returns is Bool:
            output = "Bool.to_u32(result)"
        lines.extend([f"    BendPy.ret({output})", ""])
    lines.extend(["def BendPy.dispatch(which: U32) -> IO(Unit):", "  match which:"])
    for index in range(len(exports)):
        lines.extend([f"    case {index}:", f"      BendPy.fn{index}()"])
    lines.extend(
        [
            "    case _:",
            "      BendPy.ret(0)",
            "",
            "def main() -> IO(Unit):",
            "  do IO<Unit>:",
            "    which : U32 <- BendPy.select()",
            "    BendPy.dispatch(which)",
            "",
        ]
    )
    return "\n".join(lines)

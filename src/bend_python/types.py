"""Explicit export signatures for the native ABI."""

from __future__ import annotations

import operator
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class Scalar(Enum):
    """Scalar values supported by both the Python codec and Bend wrapper."""

    U32 = "U32"
    BOOL = "Bool"
    F32 = "F32"

    def encode(self, value: object) -> int:
        if self is Scalar.BOOL:
            if not isinstance(value, bool):
                raise TypeError("Bool requires a Python bool")
            return int(value)
        if self is Scalar.U32:
            if isinstance(value, bool):
                raise TypeError("U32 requires an integer, not bool")
            try:
                word = operator.index(value)  # type: ignore[arg-type]
            except TypeError:
                raise TypeError("U32 requires an integer") from None
            if not 0 <= word <= 0xFFFFFFFF:
                raise OverflowError("U32 must be between 0 and 4294967295")
            return word
        if isinstance(value, (bool, str, bytes, bytearray)):
            raise TypeError("F32 requires a real number")
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise TypeError("F32 requires a real number") from None
        return int(struct.unpack("<I", struct.pack("<f", number))[0])

    def decode(self, word: int) -> int | float | bool:
        if self is Scalar.BOOL:
            if word not in (0, 1):
                raise ValueError("native Bool is neither zero nor one")
            return bool(word)
        if self is Scalar.F32:
            return float(struct.unpack("<f", struct.pack("<I", word))[0])
        return word


U32 = Scalar.U32
Bool = Scalar.BOOL
F32 = Scalar.F32


@dataclass(frozen=True, init=False)
class Function:
    """Describe one monomorphic pure Bend function to export.

    ``name`` optionally selects a dotted Bend definition independently of the
    Python export name. Arguments and the result are checked by Bend at build time.
    """

    args: tuple[Scalar, ...]
    returns: Scalar
    name: str | None

    def __init__(self, args: Iterable[Scalar], returns: Scalar, *, name: str | None = None) -> None:
        arguments = tuple(args)
        if not all(isinstance(arg, Scalar) for arg in arguments):
            raise TypeError("arguments must be U32, Bool, or F32")
        if not isinstance(returns, Scalar):
            raise TypeError("return type must be U32, Bool, or F32")
        if len(arguments) > 64:
            raise ValueError("an export supports at most 64 arguments")
        object.__setattr__(self, "args", arguments)
        object.__setattr__(self, "returns", returns)
        object.__setattr__(self, "name", name)

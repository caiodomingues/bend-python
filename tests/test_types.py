import math

import pytest

from bend_python import F32, U32, Bool, Function
from bend_python._generate import validate_exports


@pytest.mark.parametrize("value", [0, 1, 2**31, 2**32 - 1])
def test_u32_boundaries(value):
    assert U32.decode(U32.encode(value)) == value


@pytest.mark.parametrize("value", [-1, 2**32, 2**100])
def test_u32_rejects_out_of_range(value):
    with pytest.raises(OverflowError):
        U32.encode(value)


@pytest.mark.parametrize("value", [True, False, "1", 1.5, None])
def test_u32_rejects_non_integers(value):
    with pytest.raises(TypeError):
        U32.encode(value)


def test_u32_accepts_integer_index_protocol():
    class Word:
        def __index__(self):
            return 42

    assert U32.encode(Word()) == 42


@pytest.mark.parametrize("value", [0, 1, "True", None])
def test_bool_is_not_an_integer(value):
    with pytest.raises(TypeError):
        Bool.encode(value)


def test_f32_rounding_and_special_values():
    assert F32.decode(F32.encode(0.1)) == 0.10000000149011612
    assert math.copysign(1, F32.decode(F32.encode(-0.0))) == -1
    assert math.isnan(F32.decode(F32.encode(float("nan"))))
    assert F32.decode(F32.encode(float("inf"))) == float("inf")
    with pytest.raises(OverflowError):
        F32.encode(1e100)


@pytest.mark.parametrize("value", [True, "1.0", 1j, None])
def test_f32_rejects_non_real_inputs(value):
    with pytest.raises(TypeError):
        F32.encode(value)


@pytest.mark.parametrize("name", ["close", "functions", "__dict__", "a.b", "for", "a;exit(1)"])
def test_export_names_cannot_shadow_module_api(name):
    with pytest.raises(ValueError):
        validate_exports({name: Function([U32], U32)})


def test_invalid_signatures():
    with pytest.raises(TypeError):
        Function(["U32"], U32)
    with pytest.raises(TypeError):
        Function([U32], "U32")
    with pytest.raises(ValueError):
        validate_exports({"ok": Function([], U32, name="x()\nmalicious")})

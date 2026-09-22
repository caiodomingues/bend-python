from __future__ import annotations

import ctypes
import json
import math
import os
import random
import signal
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from bend_python import ClosedError, CompatibilityError, NativeError, load

pytestmark = pytest.mark.native


def test_scalars_and_aliases(kernels):
    assert kernels.add(20, 22) == 42
    assert kernels.add(0xFFFFFFFF, 1) == 0
    assert kernels.choose(True, 7, 11) == 7
    assert kernels.choose(False, 7, 11) == 11
    assert kernels.lerp(10.0, 20.0, 0.25) == 12.5
    assert kernels.ready() is True
    assert kernels.double(21) == 42
    assert kernels["add"](2, 3) == 5


def test_repeated_calls_match_python(kernels):
    randomizer = random.Random(2026)
    for _ in range(10000):
        a = randomizer.randrange(2**32)
        b = randomizer.randrange(2**32)
        assert kernels.add(a, b) == (a + b) & 0xFFFFFFFF


def test_float_edge_cases(kernels):
    assert kernels.identity_f32(0.1) == 0.10000000149011612
    assert math.copysign(1, kernels.identity_f32(-0.0)) == -1
    assert math.isnan(kernels.identity_f32(float("nan")))
    assert kernels.identity_f32(float("inf")) == float("inf")


@pytest.mark.parametrize("threads", [1, 2, 4])
def test_native_parallel_results(native_artifact, threads):
    with load(native_artifact, threads=threads) as module:
        for depth in [0, 1, 5, 12, 16, 3, 15]:
            assert module.parallel_count(depth) == 2**depth


def test_python_threads_share_one_runtime_safely(kernels):
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda n: kernels.parallel_count(n), [10, 12, 8, 14] * 10))
    assert results == [2**n for n in [10, 12, 8, 14] * 10]


def test_loaded_modules_are_independent(native_artifact):
    with load(native_artifact, threads=2) as left, load(native_artifact, threads=4) as right:
        with ThreadPoolExecutor(max_workers=2) as executor:
            a = executor.submit(left.parallel_count, 16)
            b = executor.submit(right.parallel_count, 15)
            assert (a.result(), b.result()) == (65536, 32768)
        left.close()
        assert right.add(40, 2) == 42


def test_bad_arguments_do_not_poison_runtime(kernels):
    with pytest.raises(TypeError):
        kernels.add(1)
    with pytest.raises(OverflowError):
        kernels.add(-1, 2)
    with pytest.raises(TypeError):
        kernels.choose(1, 2, 3)
    assert kernels.add(20, 22) == 42


def test_close_invalidates_retained_functions(native_artifact):
    module = load(native_artifact)
    function = module.add
    assert function(1, 2) == 3
    module.close()
    module.close()
    assert module.closed
    with pytest.raises(ClosedError):
        function(1, 2)


def test_close_joins_workers_and_preserves_signal_handlers(native_artifact):
    libc = ctypes.CDLL(None)
    libc.sigaction.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
    libc.sigaction.restype = ctypes.c_int

    def handlers():
        values = []
        for sig in [signal.SIGSEGV, signal.SIGBUS, signal.SIGPIPE]:
            state = ctypes.create_string_buffer(512)
            assert libc.sigaction(sig, None, state) == 0
            values.append(bytes(state)[: ctypes.sizeof(ctypes.c_void_p)])
        return values

    before_handlers = handlers()
    before_threads = len(list(Path("/proc/self/task").iterdir()))
    with load(native_artifact, threads=4) as module:
        assert module.parallel_count(16) == 65536
        assert len(list(Path("/proc/self/task").iterdir())) >= before_threads + 4
    assert len(list(Path("/proc/self/task").iterdir())) == before_threads
    assert handlers() == before_handlers


def test_artifact_rejects_modified_signatures(native_artifact, tmp_path):
    data = json.loads(native_artifact.read_text())
    data["exports"][0]["returns"] = "Bool"
    changed = native_artifact.with_name("changed.json")
    changed.write_text(json.dumps(data))
    with pytest.raises(CompatibilityError, match="modified"):
        load(changed)


def test_artifact_rejects_platform_mismatch(native_artifact):
    data = json.loads(native_artifact.read_text())
    data["machine"] = "unsupported-cpu"
    changed = native_artifact.with_name("wrong-machine.json")
    changed.write_text(json.dumps(data))
    with pytest.raises(CompatibilityError, match="CPU"):
        load(changed)


def test_inherited_runtime_is_rejected_after_fork(kernels):
    assert kernels.parallel_count(12) == 4096
    pid = os.fork()
    if pid == 0:
        try:
            kernels.add(1, 2)
        except NativeError:
            os._exit(0)
        os._exit(1)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0

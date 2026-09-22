from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from bend_python import F32, U32, Bool, Function, build, load

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def native_artifact(tmp_path_factory):
    if sys.platform != "linux" or not shutil.which(os.environ.get("BENDPY_BEND", "bend")):
        if os.environ.get("BENDPY_REQUIRE_NATIVE") == "1":
            pytest.fail("native integration tests require Linux, Bend 2.0.25, and clang")
        pytest.skip("Linux and Bend 2.0.25 are required")
    return build(
        ROOT / "examples/kernels.bend",
        exports={
            "add": Function([U32, U32], U32),
            "choose": Function([Bool, U32, U32], U32),
            "lerp": Function([F32, F32, F32], F32),
            "parallel_count": Function([U32], U32),
            "identity_f32": Function([F32], F32),
            "ready": Function([], Bool),
            "double": Function([U32], U32, name="Math.double"),
        },
        build_dir=tmp_path_factory.mktemp("native"),
    )


@pytest.fixture
def kernels(native_artifact):
    with load(native_artifact, threads=4) as module:
        yield module

import os
import subprocess
from pathlib import Path

import pytest

from bend_python import U32, BuildError, Function, build, load

pytestmark = pytest.mark.native


def test_bend_checks_declared_export_types(native_artifact, tmp_path):
    source = tmp_path / "wrong.bend"
    source.write_text("import Base\n\ndef value() -> Bool:\n  True{}\n")
    with pytest.raises(BuildError, match="expected|mismatch"):
        build(source, exports={"value": Function([], U32)}, build_dir=tmp_path / "build")


def test_zero_argument_u32_export(native_artifact, tmp_path):
    source = tmp_path / "constant.bend"
    source.write_text("import Base\n\ndef answer() -> U32:\n  42\n")
    artifact = build(source, exports={"answer": Function([], U32)}, build_dir=tmp_path / "build")
    with load(artifact) as module:
        assert module.answer() == 42


def test_example_proofs(native_artifact):
    proof = Path(__file__).resolve().parents[1] / "examples/PROOF.bend"
    result = subprocess.run(
        [os.environ.get("BENDPY_BEND", "bend"), str(proof)],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "BEND_NO_TELEMETRY": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All terms check." in result.stdout + result.stderr


def test_loaded_artifact_does_not_need_a_compiler(native_artifact, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    with load(native_artifact) as module:
        assert module.add(10, 32) == 42

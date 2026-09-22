# Contributing

Use Python 3.10+, Linux, clang 14+, and Bend 2.0.25. WSL2 is supported.
Install development dependencies with `uv sync --locked`.

Run lint, formatting checks, mypy, the native tests, and the package build before
submitting changes. The exact commands are in the README and CI workflow.

New exported types need round-trip tests through a real compiled Bend library.
Runtime changes need concurrent-call and resource-lifecycle tests. Claims about
performance should include the workload, machine, thread count, warm-up, and
conversion/transfer costs.

Keep compiler-version adaptations isolated in `_runtime_patch.py`. Do not silently
accept another Bend version. Add a measured compatibility run before changing the pin.

The Python API is experimental and may change before 1.0.

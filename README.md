# bend-python

Call native [Bend 2](https://github.com/bendlang/bend) functions from Python.

`bend-python` builds a shared library once, then calls it in the Python process
through `ctypes`. Bend retains its CPU parallelism. Python handles application
integration; Bend owns the exported computations.

**Alpha:** Linux, Python 3.10+, Bend **2.0.25**, clang 14+. Tested on Linux x86-64
under WSL2. Run both Python and Bend inside WSL on Windows.

## Quick start

Install the [Bend 2.0.25 Linux release](https://github.com/bendlang/bend/releases/tag/v2.0.25)
and clang, then install this package:

```sh
python -m pip install "git+https://github.com/caiodomingues/bend-python.git"
```

Create `kernels.bend`:

```python
import Base

def add(a: U32, b: U32) -> U32:
  (a + b : U32)
```

Call it from Python:

```python
from bend_python import U32, Function, compile_module

with compile_module(
    "kernels.bend",
    exports={"add": Function([U32, U32], U32)},
    threads=4,
) as kernels:
    assert kernels.add(20, 22) == 42
    assert kernels.add(0xFFFFFFFF, 1) == 0
```

Compilation checks the declared signatures against the actual Bend functions.
The source file is imported unchanged. There is no subprocess per function call.

Run `python examples/quickstart.py` from this repository for integers,
booleans, floating-point values, and a parallel Bend computation.

## Supported values

| Export type | Python input | Python result |
| --- | --- | --- |
| `U32` | Integer in `0..2**32-1`; supports `__index__` | `int` |
| `Bool` | `bool` | `bool` |
| `F32` | Real number rounded to binary32 | `float` |

Import types with `from bend_python import U32, Bool, F32`. Booleans are rejected
as U32/F32 inputs. Out-of-range U32 values and overflowing finite F32 inputs
raise Python exceptions. U32 arithmetic inside Bend retains its wrapping behavior.

Use `Function([U32], U32, name="Math.double")` to export a dotted Bend
definition under a different Python name. Only monomorphic pure functions with
these argument and return types are supported initially.

## Compile once, load later

```python
from bend_python import U32, Function, build, load

artifact = build(
    "kernels.bend",
    exports={"add": Function([U32, U32], U32)},
    build_dir="build/kernels",
)

with load(artifact, threads=4) as kernels:
    print(kernels.add(20, 22))
```

The build directory contains a JSON manifest, a native library, the generated
Bend wrapper, and a compiler log. Ship the manifest and its referenced library
together. Loading needs neither Bend nor clang, but the library still requires
a compatible Linux architecture and system libraries. These are local native
artifacts, not portable manylinux wheels.

A checksum and a compiled signature identifier detect mixed or modified
artifacts. They do not authenticate untrusted native code.

## Runtime ownership and threads

- `threads` selects the Bend worker pool; the default is 1 and the current maximum is 128.
- Calls to one loaded module are serialized. Bend parallel calls inside a function
  may use the selected workers. The native call releases Python's GIL.
- Loading an artifact twice creates independent runtime state.
- `close()` waits for an active call, joins workers, and unmaps runtime heap/stacks.
  Retained function objects reject calls after close. Prefer a context manager.
- The adapter leaves Python's process signal handlers unchanged.
- Load a fresh module in a child process; using an inherited module after `fork`
  is rejected. Prefer multiprocessing's `spawn` mode.
- Bend reserves large virtual memory regions; reserved address space is not resident RAM.
  Closing releases runtime mappings; this package does not explicitly unload library code.

## Boundaries

This release runs on the **CPU**. CUDA/Metal, native Windows DLLs, arbitrary
datatypes, callbacks, and NumPy arrays are not supported yet.

Bend has no public native embedding ABI. This package therefore pins one
compiler version and adapts three emitted runtime functions to preserve host
signal handlers and support worker shutdown. Other versions are rejected.
See [the embedding notes](docs/embedding.md).

Python validates arguments and reports build/boundary errors as exceptions.
**A fatal Bend runtime error, including allocation failure, can still terminate
the Python process.** This is an in-process native extension, not a sandbox.
Run untrusted or unbounded computations in an isolated process.

Bend proofs apply to their source-level statements. They do not verify the
compiler, this adapter, ctypes, or arbitrary foreign code. The example proofs
can be checked separately:

```sh
bend examples/PROOF.bend
```

Source import paths currently need ASCII letters, digits, underscores, hyphens,
dots, and slashes. Use a source directory without spaces.

## Toolchain configuration

`BENDPY_BEND` and `BENDPY_CC` select executable paths. The `bend=` and `cc=`
build arguments override them. Set `timeout=` to change the per-command build
timeout (120 seconds by default).

`python -m bend_python doctor` reports platform and tool locations.

## Development

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy
BENDPY_REQUIRE_NATIVE=1 uv run pytest -q
uv build
```

Native tests compile real Bend source and exercise the resulting libraries.
They cover repeated calls, floating-point edge cases, parallel workers, Python
threads, independent runtimes, artifact mismatches, fork rejection, and cleanup.
`BENDPY_REQUIRE_NATIVE=1` makes a missing native toolchain a failure instead of a skip.

## Upstream

This project is a concrete consumer for Bend's planned
[native library target](https://github.com/bendlang/bend/issues/813).
The [godot-bend integration](https://github.com/aricarmo/godot-bend) demonstrated
the feasibility of embedding the runtime and informed the initial investigation.
The Python adapter is an independent implementation.

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

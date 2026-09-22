# Embedding Bend 2.0.25

The first version exports explicitly declared, monomorphic pure scalar functions.
A generated Bend module imports the user's source and dispatches to those functions.
Foreign effects read arguments from a temporary C word buffer and deliver the result.
Bend checks the wrapper before generating C, so an incorrect export signature fails
at compilation.

Python loads a private copy of each compiled library with local symbol visibility.
This gives each module its own Bend globals. A manifest describes the exports and
platform; its contract hash is compiled into the library. ctypes transfers scalar
words and releases the GIL during native execution. Python and C locks serialize
calls and shutdown for one runtime.

## Lifecycle

The library initializes the corpus and caller stack on the first invocation.
Every invocation starts a fresh generated IO action over the same corpus.
The dispatch action calls the pure exported definition and completes synchronously.
The adapter does not run the CLI event loop, install its wake pipe, or enable GPU use.

Closing requests worker termination, wakes the pool, joins every worker, and unmaps
the caller stack and corpus. The object cannot be restarted. Closing an unused
module creates no runtime resources. Python finalization is a fallback; explicit
context-manager ownership is preferable.

A forked child cannot safely use a parent's pthread state. Both sides of the
boundary check process identity before entering their locks.

## Emitted-runtime adaptations

Bend's compiler is not modified. After generation, the package adapts:

1. `pool_stack`: retain the guarded virtual stack without installing process-wide
   signal handlers or a thread-local alternate signal stack.
2. `pool_work`: observe a shutdown flag while waiting, unmap its stack, and exit.
3. `pool_open`: retain joinable thread IDs.

These edits depend on private symbols and the exact Bend release. Pattern checks
fail closed when required runtime shapes are absent. They are not a compatibility
promise for another version.

The ordinary native failure mechanism is retained. A runtime fail-stop may end
the entire Python process. Recoverable native runtime errors, configurable memory
budgets, and a public instance-owned runtime would be useful upstream capabilities.

## What a public ABI would replace

A supported compiler target could generate an export schema and C declarations,
define setup/call/close operations, specify ownership and failure behavior, and
make concurrency/reentrancy contracts explicit. This would remove the generated
IO dispatch and private runtime edits here.

This document records integration requirements; it is not an upstream proposal
that has been accepted or submitted.

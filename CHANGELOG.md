# Changelog

## 0.1.0

- Compile pure Bend functions into native libraries and call them from Python.
- Support U32, Bool, F32, export aliases, and explicit signatures.
- Reuse compiled artifacts without a compiler at runtime.
- Configure CPU workers; serialize calls per instance and isolate loaded modules.
- Close worker threads and runtime mappings without replacing Python signal handlers.
- Check actual native execution, lifecycle behavior, and source-level example laws.

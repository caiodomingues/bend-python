"""Version-specific embedding adaptations for the emitted Bend 2.0.25 C runtime."""

from .errors import CompatibilityError

_STACK = """#define BP_STACK_BYTES ((1ull << 31) + 16384)
static _Atomic bool bp_pool_stop;
static pthread_t bp_workers[CUBE_T];
static u32 bp_worker_count;

static Term* pool_stack(void) {
  u64 len = 1ull << 31;
  char* p = pool_mmap(BP_STACK_BYTES);
  if (mprotect(p + len, 16384, PROT_NONE) != 0) {
    err_fail("stack guard failed");
  }
  return (Term*)p;
}

"""

_OPEN = """OUTLINE void pool_open(void) {
  if (bp_worker_count != 0) return;
  for (u32 w = 0; w < pool_size; w += 1) {
    if (pthread_create(&bp_workers[w], NULL, pool_work, (void*)(uintptr_t)w)) {
      err_fail("pthread_create");
    }
    bp_worker_count += 1;
  }
}

"""


def _replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise CompatibilityError("Bend runtime layout changed; refusing an unverified adapter")
    return source.replace(old, new, 1)


def adapt_runtime(source: str) -> str:
    try:
        stack = source.index("static Term* pool_stack(void) {")
        worker = source.index("static void* pool_work(void* arg) {", stack)
        pool_open = source.index("OUTLINE void pool_open(void) {", worker)
        pool_end = source.index("\n}\n", pool_open) + 3
    except ValueError as exc:
        raise CompatibilityError("unsupported Bend runtime layout") from exc
    worker_code = source[worker:pool_open]
    worker_code = _replace_once(
        worker_code,
        "while (atomic_load_explicit(&pool_tick, memory_order_acquire) == seen)",
        "while (!atomic_load_explicit(&bp_pool_stop, memory_order_acquire) && "
        "atomic_load_explicit(&pool_tick, memory_order_acquire) == seen)",
    )
    worker_code = _replace_once(
        worker_code,
        "    pthread_mutex_unlock(&pool_lock);\n    seen =",
        "    bool stopping = atomic_load_explicit(&bp_pool_stop, memory_order_acquire);\n"
        "    pthread_mutex_unlock(&pool_lock);\n"
        "    if (stopping) {\n"
        "      munmap(stk, BP_STACK_BYTES);\n"
        "      return NULL;\n"
        "    }\n"
        "    seen =",
    )
    return source[:stack] + _STACK + worker_code + _OPEN + source[pool_end:]

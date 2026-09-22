// Included after Bend's runtime; generated configuration precedes this file.
static pthread_mutex_t bp_lock = PTHREAD_MUTEX_INITIALIZER;
static const uint32_t *bp_args;
static uint32_t bp_function;
static uint32_t bp_result;
static bool bp_returned;
static bool bp_up;
static bool bp_closed;
static pid_t bp_pid;

Term bendpy_select_run(Env e, Term *f, IoWork *w) {
  return (Term)bp_function;
}

#ifdef CID_BENDPY_ARG_U32
Term bendpy_arg_u32_run(Env e, Term *f, IoWork *w) {
  return (Term)bp_args[(u32)f[0]];
}
#endif

#ifdef CID_BENDPY_ARG_F32
Term bendpy_arg_f32_run(Env e, Term *f, IoWork *w) {
  return (Term)bp_args[(u32)f[0]];
}
#endif

Term bendpy_ret_run(Env e, Term *f, IoWork *w) {
  bp_result = (u32)f[0];
  bp_returned = true;
  return term_pak(CID_UNIT, 0);
}

static void __attribute__((constructor)) bp_effects(void) {
  bp_pid = getpid();
  io_eff(CID_BENDPY_SELECT, bendpy_select_run, 0);
#ifdef CID_BENDPY_ARG_U32
  io_eff(CID_BENDPY_ARG_U32, bendpy_arg_u32_run, 0);
#endif
#ifdef CID_BENDPY_ARG_F32
  io_eff(CID_BENDPY_ARG_F32, bendpy_arg_f32_run, 0);
#endif
  io_eff(CID_BENDPY_RET, bendpy_ret_run, 0);
}

#define BP_API __attribute__((visibility("default")))

BP_API const char *bendpy_abi(void) {
  return BP_ABI;
}

BP_API uint32_t bendpy_thread_limit(void) {
  return CUBE_T;
}

BP_API int bendpy_call(uint32_t fn, const uint32_t *args, uint32_t argc,
                      uint32_t threads, uint32_t *result) {
  if (getpid() != bp_pid) return 4;
  if (fn >= BP_EXPORTS || argc != bp_argc[fn] || result == NULL ||
      (argc != 0 && args == NULL) || threads < 1 || threads > CUBE_T) return 2;
  pthread_mutex_lock(&bp_lock);
  if (bp_closed) {
    pthread_mutex_unlock(&bp_lock);
    return 1;
  }
  if (!bp_up) {
    corpus_setup(false, threads, 0);
    io_stk = pool_stack();
    bp_up = true;
  }
  bp_args = args;
  bp_function = fn;
  bp_returned = false;
  Env e = { CORPUS, ALC[0] };
  io_spawn(corpus_eval(CORPUS, term_tsk(MAIN_FID,
    task_node(e, MAIN_FID, TERM_HOLE, 0, 0))));
  int status = 0;
  while (io_runs.head != NULL) {
    if (io_step(e, io_pop(&io_runs)) >= 0) {
      status = 3;
      break;
    }
  }
  if (io_live != 0 || !bp_returned) status = 3;
  if (status == 0) *result = bp_result;
  bp_args = NULL;
  pthread_mutex_unlock(&bp_lock);
  return status;
}

BP_API int bendpy_close(void) {
  if (getpid() != bp_pid) return 4;
  pthread_mutex_lock(&bp_lock);
  if (!bp_closed && bp_up) {
    pthread_mutex_lock(&pool_lock);
    atomic_store_explicit(&bp_pool_stop, true, memory_order_release);
    pthread_cond_broadcast(&pool_wake);
    pthread_mutex_unlock(&pool_lock);
    for (u32 i = 0; i < bp_worker_count; i += 1) {
      pthread_join(bp_workers[i], NULL);
    }
    munmap(io_stk, BP_STACK_BYTES);
    munmap(CORPUS, corpus_size);
    io_stk = NULL;
    CORPUS = NULL;
  }
  bp_closed = true;
  pthread_mutex_unlock(&bp_lock);
  return 0;
}

from pathlib import Path

from bend_python import F32, U32, Bool, Function, compile_module

with compile_module(
    Path(__file__).with_name("kernels.bend"),
    exports={
        "add": Function([U32, U32], U32),
        "choose": Function([Bool, U32, U32], U32),
        "lerp": Function([F32, F32, F32], F32),
        "parallel_count": Function([U32], U32),
    },
    threads=4,
) as kernels:
    assert kernels.add(20, 22) == 42
    assert kernels.choose(False, 7, 11) == 11
    assert kernels.lerp(10.0, 20.0, 0.25) == 12.5
    assert kernels.parallel_count(16) == 65536
    print("add:", kernels.add(20, 22))
    print("choose:", kernels.choose(False, 7, 11))
    print("lerp:", kernels.lerp(10.0, 20.0, 0.25))
    print("parallel_count:", kernels.parallel_count(16))

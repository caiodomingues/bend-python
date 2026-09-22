import Base
import ./kernels.bend as Kernels

law choose_true:
  for a: U32
  for b: U32
  {Kernels.choose(True{}, a, b) == a : U32}

law choose_false:
  for a: U32
  for b: U32
  {Kernels.choose(False{}, a, b) == b : U32}

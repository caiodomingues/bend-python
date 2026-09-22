import Base

def add(a: U32, b: U32) -> U32:
  (a + b : U32)

def choose(flag: Bool, a: U32, b: U32) -> U32:
  match flag:
    case True{}:
      a
    case False{}:
      b

def lerp(+a: F32, b: F32, t: F32) -> F32:
  (a + ((b - a : F32) * t : F32) : F32)

def tree(+depth: Nat) -> U32:
  match depth:
    case 0n:
      1
    case 1n+rest:
      left right = tree(rest) tree(rest)
      (left + right : U32)

def parallel_count(depth: U32) -> U32:
  tree(U32.to_nat(depth))

def identity_f32(value: F32) -> F32:
  value

def ready() -> Bool:
  True{}

def Math.double(value: U32) -> U32:
  (value * 2 : U32)

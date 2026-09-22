"""Errors raised before or at the native boundary."""


class BendError(Exception):
    """Base exception for bend-python."""


class BuildError(BendError):
    """A toolchain, source, or native compilation check failed."""


class CompatibilityError(BendError):
    """The compiler, platform, or artifact ABI is unsupported."""


class NativeError(BendError):
    """The native boundary rejected a call or encountered an invalid state."""


class ClosedError(NativeError):
    """A function belongs to a closed module."""

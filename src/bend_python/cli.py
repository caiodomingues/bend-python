"""Small diagnostic CLI for the Python integration."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys

from . import BEND_VERSION, __version__


def main() -> int:
    parser = argparse.ArgumentParser(description="Call native Bend functions from Python")
    parser.add_argument("--version", action="version", version=f"bend-python {__version__}")
    parser.add_argument("command", choices=["doctor"], help="print build tool locations")
    parser.parse_args()
    print(f"bend-python {__version__}; requires Bend {BEND_VERSION}")
    print(f"Python {platform.python_version()} on {sys.platform}/{platform.machine()}")
    ready = sys.platform == "linux"
    for variable, default in (("BENDPY_BEND", "bend"), ("BENDPY_CC", "clang")):
        executable = os.environ.get(variable, default)
        found = shutil.which(executable)
        print(f"{default}: {found or 'not found'}")
        ready = ready and found is not None
    if sys.platform != "linux":
        print("Use a Linux Python environment; Windows users can use WSL2.")
    return 0 if ready else 1

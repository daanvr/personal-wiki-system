# Calendar module internal library.
#
# Importing this package also makes the shared modules/_shared package
# importable for the module's helpers.
import sys
from pathlib import Path

_MODULES_DIR = str(Path(__file__).resolve().parents[2])
if _MODULES_DIR not in sys.path:
    sys.path.insert(0, _MODULES_DIR)

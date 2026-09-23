"""
Makes the `app` package importable regardless of the directory pytest
is invoked from.

Without this, `pytest ai-layer/tests/` from the repository root fails
with ModuleNotFoundError: No module named 'app', while the same tests
pass when run from inside ai-layer/.
"""

import sys
from pathlib import Path

AI_LAYER_DIR = Path(__file__).resolve().parent

if str(AI_LAYER_DIR) not in sys.path:
    sys.path.insert(0, str(AI_LAYER_DIR))

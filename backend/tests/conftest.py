import os
import sys

# Tests live one level deep — put the backend root on sys.path so
# ``from engines.decay_score import ...`` works without an install step.
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

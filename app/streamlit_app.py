import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.Home
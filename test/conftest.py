import os
import sys
from pathlib import Path

# Ensure `src/` is on sys.path so tests can import project modules
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Configure Qt for headless test runs and quieter logs
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_LOGGING_RULES', 'qt.qpa.*=false')
# Prefer PyQt6 for pytest-qt to match project imports
os.environ.setdefault('PYTEST_QT_API', 'pyqt6')

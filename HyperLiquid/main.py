"""
Root Proxy Entrypoint for HL_Monarch.
Allows executing commands seamlessly from root project directory.
"""
import sys
from pathlib import Path

# Add HL_Monarch to path and delegate
monarch_dir = Path(__file__).resolve().parent / "HL_Monarch"
if str(monarch_dir) not in sys.path:
    sys.path.insert(0, str(monarch_dir))

from main import main

if __name__ == "__main__":
    main()

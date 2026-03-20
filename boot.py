"""Boot the Open Control CLI while preserving nanobot runtime compatibility."""
import sys
from pathlib import Path

# Ensure vendor/nanobot is on sys.path so 'import nanobot' resolves there
_vendor = str(Path(__file__).parent / "vendor" / "nanobot")
if _vendor not in sys.path:
    sys.path.insert(0, _vendor)

# Ensure vendor/claude-code is on sys.path so 'import claude_code' resolves there
_cc_vendor = str(Path(__file__).parent / "vendor" / "claude-code")
if _cc_vendor not in sys.path:
    sys.path.insert(0, _cc_vendor)

# Re-export the CLI app (mc commands are still registered inside nanobot.cli.commands)
from nanobot.cli.commands import app as cli  # noqa: E402

__all__ = ["cli"]

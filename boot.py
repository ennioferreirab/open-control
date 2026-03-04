"""Boot: entry point that ensures vendor/nanobot is importable and exposes the CLI."""
import sys
from pathlib import Path

# Ensure vendor/nanobot is on sys.path so 'import nanobot' resolves there
_vendor = str(Path(__file__).parent / "vendor" / "nanobot")
if _vendor not in sys.path:
    sys.path.insert(0, _vendor)

# Re-export the CLI app (mc commands are registered inside nanobot.cli.commands)
from nanobot.cli.commands import app as cli  # noqa: E402

__all__ = ["cli"]

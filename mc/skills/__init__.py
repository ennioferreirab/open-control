"""MC Skills — Mission Control builtin skills directory.

Exposes MC_SKILLS_DIR so that gateway can discover and distribute
MC-specific skills to the workspace alongside the mc-owned builtin skills.
"""

from pathlib import Path

MC_SKILLS_DIR: Path = Path(__file__).parent

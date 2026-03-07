"""Compatibility bridge to the legacy mention watcher module."""

import sys

from mc.mentions import watcher as _impl

sys.modules[__name__] = _impl

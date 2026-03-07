"""Compatibility bridge to the legacy mention handler module."""

import sys

from mc.mentions import handler as _impl

sys.modules[__name__] = _impl

"""Compatibility bridge to the legacy ask-user handler module."""

import sys

from mc.ask_user import handler as _impl

sys.modules[__name__] = _impl

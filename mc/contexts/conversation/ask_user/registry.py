"""Compatibility bridge to the legacy ask-user registry module."""

import sys

from mc.ask_user import registry as _impl

sys.modules[__name__] = _impl

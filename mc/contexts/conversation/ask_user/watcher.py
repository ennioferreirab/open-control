"""Compatibility bridge to the legacy ask-user watcher module."""

import sys

from mc.ask_user import watcher as _impl

sys.modules[__name__] = _impl

"""Compatibility facade for :mod:`mc.runtime.gateway`."""

import sys

from mc.runtime import gateway as _impl

sys.modules[__name__] = _impl

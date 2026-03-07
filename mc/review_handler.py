"""Compatibility facade for :mod:`mc.contexts.review.handler`."""

import sys

from mc.contexts.review import handler as _impl

sys.modules[__name__] = _impl

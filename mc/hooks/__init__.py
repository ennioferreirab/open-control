"""Hook system for extensible event handling."""

from mc.hooks.discovery import discover_handlers
from mc.hooks.handler import BaseHandler

__all__ = ["BaseHandler", "discover_handlers"]

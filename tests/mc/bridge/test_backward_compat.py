"""Backward compatibility tests for mc.bridge package.

Ensures that all imports that worked with the old mc/bridge.py module
still work after converting to mc/bridge/ package.
"""


class TestImports:
    def test_import_convex_bridge(self):
        """ConvexBridge class is importable from mc.bridge."""
        from mc.bridge import ConvexBridge

        assert ConvexBridge is not None

    def test_import_key_conversion_functions(self):
        """Key conversion functions are importable from mc.bridge."""
        from mc.bridge import (
            _to_camel_case,
            _to_snake_case,
        )

        assert _to_camel_case("foo_bar") == "fooBar"
        assert _to_snake_case("fooBar") == "foo_bar"

    def test_import_constants(self):
        """Retry constants are importable from mc.bridge."""
        from mc.bridge import BACKOFF_BASE_SECONDS, MAX_RETRIES

        assert MAX_RETRIES == 3
        assert BACKOFF_BASE_SECONDS == 1

    def test_convex_client_in_namespace(self):
        """ConvexClient is in mc.bridge namespace (needed for @patch)."""
        from mc.bridge import ConvexClient

        assert ConvexClient is not None

    def test_time_module_in_namespace(self):
        """time module is in mc.bridge namespace (needed for @patch)."""
        import mc.bridge

        assert hasattr(mc.bridge, "time")

    def test_os_module_in_namespace(self):
        """os module is in mc.bridge namespace (needed for @patch)."""
        import mc.bridge

        assert hasattr(mc.bridge, "os")

    def test_re_module_in_namespace(self):
        """re module is in mc.bridge namespace."""
        import mc.bridge

        assert hasattr(mc.bridge, "re")

    def test_repository_classes_importable(self):
        """Repository classes can be imported from their sub-modules."""
        from mc.bridge.repositories import (
            AgentRepository,
            BoardRepository,
            ChatRepository,
            MessageRepository,
            StepRepository,
            TaskRepository,
        )

        assert all(
            [
                AgentRepository,
                BoardRepository,
                ChatRepository,
                MessageRepository,
                StepRepository,
                TaskRepository,
            ]
        )

    def test_bridge_client_importable(self):
        """BridgeClient class can be imported from mc.bridge.client."""
        from mc.bridge.client import BridgeClient

        assert BridgeClient is not None

    def test_subscription_manager_importable(self):
        """SubscriptionManager can be imported from mc.bridge.subscriptions."""
        from mc.bridge.subscriptions import SubscriptionManager

        assert SubscriptionManager is not None

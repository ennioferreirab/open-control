"""Tests for _build_tag_attributes_context in executor.py."""

from mc.contexts.execution.executor import _build_tag_attributes_context


class TestBuildTagAttributesContextEmpty:
    """Empty/no-op scenarios."""

    def test_empty_tags_returns_empty(self):
        assert _build_tag_attributes_context([], [], []) == ""

    def test_no_attr_values_returns_empty(self):
        tags = ["client"]
        catalog = [{"id": "attr1", "name": "priority", "type": "text"}]
        assert _build_tag_attributes_context(tags, [], catalog) == ""

    def test_no_catalog_returns_empty(self):
        tags = ["client"]
        values = [{"tag_name": "client", "attribute_id": "attr1", "value": "high"}]
        assert _build_tag_attributes_context(tags, values, []) == ""

    def test_none_tags_returns_empty(self):
        """Falsy tags list returns empty."""
        assert (
            _build_tag_attributes_context(
                [],
                [{"tag_name": "a", "attribute_id": "x", "value": "v"}],
                [{"id": "x", "name": "n"}],
            )
            == ""
        )


class TestBuildTagAttributesContextBasic:
    """Basic formatting tests."""

    def test_single_tag_single_attribute(self):
        tags = ["client"]
        catalog = [{"id": "attr1", "name": "priority", "type": "text"}]
        values = [{"tag_name": "client", "attribute_id": "attr1", "value": "high"}]

        result = _build_tag_attributes_context(tags, values, catalog)
        assert "[Task Tag Attributes]" in result
        assert "client: priority=high" in result

    def test_single_tag_multiple_attributes(self):
        tags = ["project"]
        catalog = [
            {"id": "attr1", "name": "deadline", "type": "date"},
            {"id": "attr2", "name": "status", "type": "select"},
        ]
        values = [
            {"tag_name": "project", "attribute_id": "attr1", "value": "2026-03-01"},
            {"tag_name": "project", "attribute_id": "attr2", "value": "active"},
        ]

        result = _build_tag_attributes_context(tags, values, catalog)
        assert "[Task Tag Attributes]" in result
        assert "project: deadline=2026-03-01, status=active" in result

    def test_multiple_tags_with_attributes(self):
        tags = ["client", "billing"]
        catalog = [
            {"id": "attr1", "name": "priority", "type": "text"},
            {"id": "attr2", "name": "amount", "type": "number"},
        ]
        values = [
            {"tag_name": "client", "attribute_id": "attr1", "value": "urgent"},
            {"tag_name": "billing", "attribute_id": "attr2", "value": "500"},
        ]

        result = _build_tag_attributes_context(tags, values, catalog)
        assert "[Task Tag Attributes]" in result
        assert "client: priority=urgent" in result
        assert "billing: amount=500" in result

    def test_tag_order_matches_input(self):
        """Tags should appear in the same order as the input tags list."""
        tags = ["beta", "alpha"]
        catalog = [{"id": "a1", "name": "x", "type": "text"}]
        values = [
            {"tag_name": "alpha", "attribute_id": "a1", "value": "v1"},
            {"tag_name": "beta", "attribute_id": "a1", "value": "v2"},
        ]

        result = _build_tag_attributes_context(tags, values, catalog)
        lines = result.strip().split("\n")
        assert lines[0] == "[Task Tag Attributes]"
        assert lines[1].startswith("beta:")
        assert lines[2].startswith("alpha:")


class TestBuildTagAttributesContextFiltering:
    """Filtering/edge-case behavior."""

    def test_empty_values_excluded(self):
        """Attributes with empty string value should be excluded."""
        tags = ["client"]
        catalog = [
            {"id": "attr1", "name": "priority", "type": "text"},
            {"id": "attr2", "name": "deadline", "type": "date"},
        ]
        values = [
            {"tag_name": "client", "attribute_id": "attr1", "value": "high"},
            {"tag_name": "client", "attribute_id": "attr2", "value": ""},
        ]

        result = _build_tag_attributes_context(tags, values, catalog)
        assert "priority=high" in result
        assert "deadline" not in result

    def test_all_empty_values_returns_empty(self):
        """If all values are empty strings, section should not appear."""
        tags = ["client"]
        catalog = [{"id": "attr1", "name": "priority", "type": "text"}]
        values = [{"tag_name": "client", "attribute_id": "attr1", "value": ""}]

        result = _build_tag_attributes_context(tags, values, catalog)
        assert result == ""

    def test_tag_not_in_task_tags_excluded(self):
        """Values for tags not in the task's tags list should be excluded."""
        tags = ["active"]
        catalog = [{"id": "attr1", "name": "priority", "type": "text"}]
        values = [
            {"tag_name": "active", "attribute_id": "attr1", "value": "high"},
            {"tag_name": "removed", "attribute_id": "attr1", "value": "low"},
        ]

        result = _build_tag_attributes_context(tags, values, catalog)
        assert "active: priority=high" in result
        assert "removed" not in result

    def test_tags_without_values_omitted(self):
        """Tags that have no attribute values should not appear in output."""
        tags = ["client", "empty-tag"]
        catalog = [{"id": "attr1", "name": "priority", "type": "text"}]
        values = [{"tag_name": "client", "attribute_id": "attr1", "value": "high"}]

        result = _build_tag_attributes_context(tags, values, catalog)
        assert "client: priority=high" in result
        assert "empty-tag" not in result

    def test_unknown_attribute_id_skipped(self):
        """Values referencing unknown attribute IDs should be skipped."""
        tags = ["client"]
        catalog = [{"id": "attr1", "name": "priority", "type": "text"}]
        values = [
            {"tag_name": "client", "attribute_id": "attr1", "value": "high"},
            {"tag_name": "client", "attribute_id": "unknown_id", "value": "mystery"},
        ]

        result = _build_tag_attributes_context(tags, values, catalog)
        assert "priority=high" in result
        assert "mystery" not in result


class TestBuildTagAttributesContextBridgeKeys:
    """Test compatibility with bridge key conversion formats."""

    def test_underscore_id_key(self):
        """Bridge may return _id which gets converted to 'id'."""
        tags = ["test"]
        catalog = [{"id": "abc123", "name": "field", "type": "text"}]
        values = [{"tag_name": "test", "attribute_id": "abc123", "value": "val"}]

        result = _build_tag_attributes_context(tags, values, catalog)
        assert "test: field=val" in result

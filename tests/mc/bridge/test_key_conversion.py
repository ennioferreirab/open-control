"""Unit tests for mc.bridge.key_conversion module."""

from mc.bridge.key_conversion import (
    _convert_keys_to_camel,
    _convert_keys_to_snake,
    _to_camel_case,
    _to_snake_case,
)


class TestToCamelCase:
    def test_single_word(self):
        assert _to_camel_case("name") == "name"

    def test_two_words(self):
        assert _to_camel_case("assigned_agent") == "assignedAgent"

    def test_preserves_convex_id(self):
        assert _to_camel_case("_id") == "_id"

    def test_preserves_convex_creation_time(self):
        assert _to_camel_case("_creationTime") == "_creationTime"

    def test_empty_string(self):
        assert _to_camel_case("") == ""


class TestToSnakeCase:
    def test_camel_to_snake(self):
        assert _to_snake_case("assignedAgent") == "assigned_agent"

    def test_convex_id(self):
        assert _to_snake_case("_id") == "id"

    def test_convex_creation_time(self):
        assert _to_snake_case("_creationTime") == "creation_time"

    def test_empty_string(self):
        assert _to_snake_case("") == ""


class TestConvertKeysToCamel:
    def test_flat_dict(self):
        result = _convert_keys_to_camel({"assigned_agent": "bob", "trust_level": "autonomous"})
        assert result == {"assignedAgent": "bob", "trustLevel": "autonomous"}

    def test_nested_dict(self):
        data = {"task_data": {"assigned_agent": "bob"}}
        result = _convert_keys_to_camel(data)
        assert result == {"taskData": {"assignedAgent": "bob"}}

    def test_list_of_dicts(self):
        data = [{"task_id": "1"}, {"task_id": "2"}]
        result = _convert_keys_to_camel(data)
        assert result == [{"taskId": "1"}, {"taskId": "2"}]

    def test_primitive_passthrough(self):
        assert _convert_keys_to_camel("hello") == "hello"
        assert _convert_keys_to_camel(42) == 42
        assert _convert_keys_to_camel(None) is None

    def test_values_not_converted(self):
        result = _convert_keys_to_camel({"status": "in_progress"})
        assert result == {"status": "in_progress"}


class TestConvertKeysToSnake:
    def test_flat_dict(self):
        result = _convert_keys_to_snake({"assignedAgent": "bob", "trustLevel": "auto"})
        assert result == {"assigned_agent": "bob", "trust_level": "auto"}

    def test_nested_dict(self):
        data = {"taskData": {"assignedAgent": "bob"}}
        result = _convert_keys_to_snake(data)
        assert result == {"task_data": {"assigned_agent": "bob"}}

    def test_primitive_passthrough(self):
        assert _convert_keys_to_snake("hello") == "hello"
        assert _convert_keys_to_snake(42) == 42
        assert _convert_keys_to_snake(None) is None

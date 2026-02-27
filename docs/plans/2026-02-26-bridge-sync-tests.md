# Bridge & Sync Tests — Cleanup + Cobertura Real

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminar testes inúteis e adicionar testes que validam comportamentos reais do bridge (key conversion, retry, polling deduplication).

**Architecture:** Criar um novo arquivo `tests/mc/test_bridge.py` focado em unit tests do bridge.py. Remover testes que não testam comportamento (só inspecionam source code). Melhorar os testes de async_subscribe que existem.

**Tech Stack:** Python, pytest, pytest-asyncio, unittest.mock

---

### Task 1: Remover teste inútil — `test_uses_get_running_loop`

**Racional:** Este teste lê o source code com `inspect.getsource` e verifica se a string `"get_running_loop"` está presente. Isso é um lint check, não um teste de comportamento. Se alguém mudar o nome da variável interna sem mudar o comportamento, o teste quebra. Se alguém introduzir um bug real, o teste passa igual.

**Files:**
- Modify: `tests/mc/test_gateway.py:1017-1029`

**Step 1: Deletar o teste**

Remover o método `test_uses_get_running_loop` da classe `TestBridgeAsyncSubscribe`.

```python
# DELETAR este método inteiro:
@pytest.mark.asyncio
async def test_uses_get_running_loop(self):
    """async_subscribe should use asyncio.get_running_loop(), not get_event_loop()."""
    from nanobot.mc.bridge import ConvexBridge

    bridge = MagicMock(spec=ConvexBridge)
    import inspect
    source = inspect.getsource(ConvexBridge.async_subscribe)
    assert "get_running_loop" in source
    assert "get_event_loop" not in source
```

**Step 2: Rodar os testes pra confirmar que nada quebrou**

Run: `uv run pytest tests/mc/test_gateway.py::TestBridgeAsyncSubscribe -v`
Expected: 2 tests PASS (os dois restantes: `test_poll_retries_on_query_error`, `test_poll_exhausted_sends_error_sentinel`)

**Step 3: Commit**

```bash
git add tests/mc/test_gateway.py
git commit -m "test: remove source-inspection test that doesn't test behavior"
```

---

### Task 2: Criar `test_bridge.py` — testes de key conversion

**Racional:** `_to_camel_case`, `_to_snake_case`, `_convert_keys_to_camel`, `_convert_keys_to_snake` são usados em TODA operação bridge. Zero testes hoje. São funções puras — testes simples e determinísticos.

**Files:**
- Create: `tests/mc/test_bridge.py`

**Step 1: Escrever os testes**

```python
"""Unit tests for ConvexBridge core functionality."""

from nanobot.mc.bridge import (
    _to_camel_case,
    _to_snake_case,
    _convert_keys_to_camel,
    _convert_keys_to_snake,
)


class TestToCamelCase:
    """Test snake_case → camelCase conversion."""

    def test_simple(self):
        assert _to_camel_case("task_id") == "taskId"

    def test_multiple_underscores(self):
        assert _to_camel_case("agent_display_name") == "agentDisplayName"

    def test_no_underscores(self):
        assert _to_camel_case("status") == "status"

    def test_preserves_convex_underscore_prefix(self):
        """Convex system fields like _id, _creationTime must pass through unchanged."""
        assert _to_camel_case("_id") == "_id"
        assert _to_camel_case("_creationTime") == "_creationTime"


class TestToSnakeCase:
    """Test camelCase → snake_case conversion."""

    def test_simple(self):
        assert _to_snake_case("taskId") == "task_id"

    def test_multiple_capitals(self):
        assert _to_snake_case("agentDisplayName") == "agent_display_name"

    def test_no_capitals(self):
        assert _to_snake_case("status") == "status"

    def test_convex_id_becomes_id(self):
        """_id → id (strips underscore prefix, no camelCase to split)."""
        assert _to_snake_case("_id") == "id"

    def test_convex_creation_time(self):
        """_creationTime → creation_time."""
        assert _to_snake_case("_creationTime") == "creation_time"


class TestConvertKeysToCamel:
    """Test recursive dict key conversion to camelCase."""

    def test_flat_dict(self):
        result = _convert_keys_to_camel({"task_id": "123", "agent_name": "bot"})
        assert result == {"taskId": "123", "agentName": "bot"}

    def test_nested_dict(self):
        result = _convert_keys_to_camel({
            "task_id": "123",
            "execution_plan": {"step_count": 3},
        })
        assert result == {
            "taskId": "123",
            "executionPlan": {"stepCount": 3},
        }

    def test_list_of_dicts(self):
        result = _convert_keys_to_camel([
            {"task_id": "1"},
            {"task_id": "2"},
        ])
        assert result == [{"taskId": "1"}, {"taskId": "2"}]

    def test_non_dict_passthrough(self):
        """Strings, ints, None pass through unchanged."""
        assert _convert_keys_to_camel("hello") == "hello"
        assert _convert_keys_to_camel(42) == 42
        assert _convert_keys_to_camel(None) is None

    def test_empty_dict(self):
        assert _convert_keys_to_camel({}) == {}


class TestConvertKeysToSnake:
    """Test recursive dict key conversion to snake_case."""

    def test_flat_dict(self):
        result = _convert_keys_to_snake({"taskId": "123", "agentName": "bot"})
        assert result == {"task_id": "123", "agent_name": "bot"}

    def test_nested_dict(self):
        result = _convert_keys_to_snake({
            "taskId": "123",
            "executionPlan": {"stepCount": 3},
        })
        assert result == {
            "task_id": "123",
            "execution_plan": {"step_count": 3},
        }

    def test_convex_system_fields(self):
        """_id and _creationTime should be converted properly."""
        result = _convert_keys_to_snake({
            "_id": "abc",
            "_creationTime": 1234567890,
            "taskId": "123",
        })
        assert result == {
            "id": "abc",
            "creation_time": 1234567890,
            "task_id": "123",
        }

    def test_list_of_dicts(self):
        result = _convert_keys_to_snake([{"taskId": "1"}, {"taskId": "2"}])
        assert result == [{"task_id": "1"}, {"task_id": "2"}]

    def test_non_dict_passthrough(self):
        assert _convert_keys_to_snake("hello") == "hello"
        assert _convert_keys_to_snake(42) == 42
        assert _convert_keys_to_snake(None) is None
```

**Step 2: Rodar pra verificar que passam**

Run: `uv run pytest tests/mc/test_bridge.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/mc/test_bridge.py
git commit -m "test: add unit tests for bridge key conversion functions"
```

---

### Task 3: Adicionar testes de `_mutation_with_retry`

**Racional:** O retry com backoff exponencial é o mecanismo de resiliência central do bridge. Zero testes hoje. Precisamos testar: sucesso imediato, sucesso após retry, exaustão de retries, e error activity logging.

**Files:**
- Modify: `tests/mc/test_bridge.py`

**Step 1: Escrever os testes**

Adicionar ao final de `tests/mc/test_bridge.py`:

```python
import time
from unittest.mock import MagicMock, patch

from nanobot.mc.bridge import ConvexBridge, MAX_RETRIES, BACKOFF_BASE_SECONDS


def _make_bridge():
    """Create a ConvexBridge with mocked ConvexClient (no real connection)."""
    bridge = ConvexBridge.__new__(ConvexBridge)
    bridge._client = MagicMock()
    return bridge


class TestMutationWithRetry:
    """Test _mutation_with_retry: retry logic, backoff, error activity."""

    def test_success_on_first_attempt(self):
        bridge = _make_bridge()
        bridge._client.mutation.return_value = {"taskId": "123"}

        result = bridge.mutation("tasks:create", {"title": "test"})

        assert result == {"task_id": "123"}  # camelCase → snake_case
        assert bridge._client.mutation.call_count == 1

    def test_success_on_second_attempt(self):
        bridge = _make_bridge()
        bridge._client.mutation.side_effect = [
            ConnectionError("temporary"),
            {"taskId": "123"},
        ]

        with patch("time.sleep"):  # skip actual delay
            result = bridge.mutation("tasks:create", {"title": "test"})

        assert result == {"task_id": "123"}
        assert bridge._client.mutation.call_count == 2

    def test_raises_after_max_retries(self):
        bridge = _make_bridge()
        bridge._client.mutation.side_effect = ConnectionError("permanent")

        with patch("time.sleep"), \
             patch.object(bridge, "_write_error_activity"):
            import pytest
            with pytest.raises(ConnectionError, match="permanent"):
                bridge.mutation("tasks:create", {"title": "test"})

        assert bridge._client.mutation.call_count == MAX_RETRIES + 1

    def test_writes_error_activity_on_exhaustion(self):
        bridge = _make_bridge()
        bridge._client.mutation.side_effect = ConnectionError("boom")

        with patch("time.sleep"), \
             patch.object(bridge, "_write_error_activity") as mock_error:
            import pytest
            with pytest.raises(ConnectionError):
                bridge.mutation("tasks:create", {"title": "test"})

        mock_error.assert_called_once_with("tasks:create", "boom")

    def test_backoff_delays_are_exponential(self):
        bridge = _make_bridge()
        bridge._client.mutation.side_effect = ConnectionError("fail")

        sleep_calls = []
        with patch("nanobot.mc.bridge.time.sleep", side_effect=lambda d: sleep_calls.append(d)), \
             patch.object(bridge, "_write_error_activity"):
            import pytest
            with pytest.raises(ConnectionError):
                bridge.mutation("tasks:create", {"title": "test"})

        # MAX_RETRIES=3 → delays: 1s, 2s, 4s (backoff on attempts 1, 2, 3)
        assert sleep_calls == [1, 2, 4]

    def test_converts_args_to_camel_case(self):
        bridge = _make_bridge()
        bridge._client.mutation.return_value = None

        bridge.mutation("tasks:updateStatus", {"task_id": "123", "agent_name": "bot"})

        call_args = bridge._client.mutation.call_args[0][1]
        assert call_args == {"taskId": "123", "agentName": "bot"}

    def test_none_result_not_converted(self):
        """When mutation returns None (void), don't try to convert keys."""
        bridge = _make_bridge()
        bridge._client.mutation.return_value = None

        result = bridge.mutation("tasks:delete", {"task_id": "123"})
        assert result is None
```

**Step 2: Rodar os testes**

Run: `uv run pytest tests/mc/test_bridge.py::TestMutationWithRetry -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/mc/test_bridge.py
git commit -m "test: add unit tests for mutation retry with exponential backoff"
```

---

### Task 4: Adicionar testes de `query()`

**Racional:** `query()` converte args pra camelCase, chama o client, e converte resultado pra snake_case. Simples, mas zero testes.

**Files:**
- Modify: `tests/mc/test_bridge.py`

**Step 1: Escrever os testes**

Adicionar ao final de `tests/mc/test_bridge.py`:

```python
class TestQuery:
    """Test bridge.query(): arg conversion, result conversion."""

    def test_converts_args_and_result(self):
        bridge = _make_bridge()
        bridge._client.query.return_value = {"taskId": "123", "agentName": "bot"}

        result = bridge.query("tasks:getById", {"task_id": "123"})

        # Args converted to camelCase
        bridge._client.query.assert_called_once_with("tasks:getById", {"taskId": "123"})
        # Result converted to snake_case
        assert result == {"task_id": "123", "agent_name": "bot"}

    def test_no_args_passes_empty_dict(self):
        bridge = _make_bridge()
        bridge._client.query.return_value = []

        result = bridge.query("tasks:list")

        bridge._client.query.assert_called_once_with("tasks:list", {})
        assert result == []

    def test_none_result(self):
        bridge = _make_bridge()
        bridge._client.query.return_value = None

        result = bridge.query("tasks:getById", {"task_id": "nonexistent"})
        assert result is None
```

**Step 2: Rodar os testes**

Run: `uv run pytest tests/mc/test_bridge.py::TestQuery -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/mc/test_bridge.py
git commit -m "test: add unit tests for bridge query method"
```

---

### Task 5: Melhorar testes de `async_subscribe` — deduplicação e data flow

**Racional:** Os testes existentes cobrem error recovery, mas não testam o comportamento mais importante: a deduplicação (`last_result != result`) que evita enfileirar dados repetidos.

**Files:**
- Modify: `tests/mc/test_gateway.py` (classe `TestBridgeAsyncSubscribe`)

**Step 1: Adicionar teste de deduplicação**

Adicionar à classe `TestBridgeAsyncSubscribe` em `test_gateway.py`:

```python
@pytest.mark.asyncio
async def test_deduplicates_identical_results(self):
    """When query returns the same data twice, only one item goes into the queue."""
    from nanobot.mc.bridge import ConvexBridge

    bridge = ConvexBridge.__new__(ConvexBridge)
    bridge._client = MagicMock()

    call_count = 0

    def fake_query(fn, args=None):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return [{"id": "task_1"}]  # same data 3 times
        if call_count == 4:
            return [{"id": "task_1"}, {"id": "task_2"}]  # new data
        raise asyncio.CancelledError  # stop polling

    with patch.object(bridge, "query", side_effect=fake_query):
        q = bridge.async_subscribe("tasks:listByStatus", {"status": "inbox"}, poll_interval=0.01)
        first = await asyncio.wait_for(q.get(), timeout=5.0)
        second = await asyncio.wait_for(q.get(), timeout=5.0)

    # First emission: initial data
    assert first == [{"id": "task_1"}]
    # Second emission: changed data (not the duplicate)
    assert second == [{"id": "task_1"}, {"id": "task_2"}]
    # The 3 identical results should NOT have produced 3 queue entries
    assert q.empty()
```

**Step 2: Adicionar teste de first result always emitted**

```python
@pytest.mark.asyncio
async def test_first_result_always_emitted(self):
    """Even an empty list is emitted on the first poll (it's different from None initial state)."""
    from nanobot.mc.bridge import ConvexBridge

    bridge = ConvexBridge.__new__(ConvexBridge)
    bridge._client = MagicMock()

    call_count = 0

    def fake_query(fn, args=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return []  # empty but valid
        raise asyncio.CancelledError

    with patch.object(bridge, "query", side_effect=fake_query):
        q = bridge.async_subscribe("tasks:listByStatus", {"status": "inbox"}, poll_interval=0.01)
        result = await asyncio.wait_for(q.get(), timeout=5.0)

    assert result == []
```

**Step 2: Rodar os testes**

Run: `uv run pytest tests/mc/test_gateway.py::TestBridgeAsyncSubscribe -v`
Expected: 4 tests PASS (2 existentes + 2 novos)

**Step 3: Commit**

```bash
git add tests/mc/test_gateway.py
git commit -m "test: add deduplication and first-emit tests for async_subscribe"
```

---

### Task 6: Adicionar teste de `_write_error_activity` (best-effort)

**Racional:** Este método é chamado quando retry exaure. O comportamento esperado é: escrever activity no Convex, e se ISSO também falhar, logar o erro sem propagar exceção. Nenhum teste hoje.

**Files:**
- Modify: `tests/mc/test_bridge.py`

**Step 1: Escrever os testes**

```python
class TestWriteErrorActivity:
    """Test _write_error_activity: best-effort error logging to Convex."""

    def test_writes_activity_to_convex(self):
        bridge = _make_bridge()

        bridge._write_error_activity("tasks:create", "Connection refused")

        bridge._client.mutation.assert_called_once()
        args = bridge._client.mutation.call_args[0]
        assert args[0] == "activities:create"
        assert args[1]["eventType"] == "system_error"
        assert "tasks:create" in args[1]["description"]
        assert "Connection refused" in args[1]["description"]

    def test_swallows_exception_on_failure(self):
        """If the error activity write itself fails, no exception propagates."""
        bridge = _make_bridge()
        bridge._client.mutation.side_effect = RuntimeError("Convex unreachable")

        # Should NOT raise
        bridge._write_error_activity("tasks:create", "original error")
```

**Step 2: Rodar os testes**

Run: `uv run pytest tests/mc/test_bridge.py::TestWriteErrorActivity -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/mc/test_bridge.py
git commit -m "test: add unit tests for best-effort error activity logging"
```

---

## Resumo das mudanças

| Ação | Arquivo | O que |
|------|---------|-------|
| DELETE | `test_gateway.py` | `test_uses_get_running_loop` — inspeciona source code, não testa comportamento |
| CREATE | `test_bridge.py` | 5 classes: key conversion, mutation retry, query, error activity |
| ADD | `test_gateway.py` | 2 testes: deduplicação + first-emit em `TestBridgeAsyncSubscribe` |

**Testes removidos:** 1 (inútil)
**Testes adicionados:** ~22 (todos testam comportamento real)

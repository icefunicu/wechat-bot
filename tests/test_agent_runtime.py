import asyncio
from types import SimpleNamespace

import pytest

from backend.core.agent_runtime import AgentRuntime


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChatOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def ainvoke(self, messages, config=None):
        return _FakeMessage("好的")

    async def astream(self, messages, config=None):
        for chunk in ("你", "好"):
            yield _FakeMessage(chunk)


class _FakeOpenAIEmbeddings:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def aembed_query(self, query):
        return [float(len(query))]


class _FakeCompiledGraph:
    def __init__(self, nodes):
        self.nodes = nodes

    async def ainvoke(self, state):
        current = dict(state)
        for name in ("load_context", "build_prompt"):
            updates = await self.nodes[name](current)
            current.update(updates or {})
        return current


class _FakeStateGraph:
    def __init__(self, _state_type):
        self.nodes = {}

    def add_node(self, name, fn):
        self.nodes[name] = fn

    def add_edge(self, _src, _dst):
        return None

    def compile(self):
        return _FakeCompiledGraph(self.nodes)


class _DummyMemory:
    def __init__(self):
        self.saved_messages = []
        self.updated_emotion = None

    async def get_recent_context(self, chat_id, limit):
        return [{"role": "assistant", "content": "历史回复"}]

    async def get_user_profile(self, chat_id):
        return SimpleNamespace(
            wx_id=chat_id,
            context_facts=["旧事实"],
            personality="冷静",
            relationship="unknown",
            message_count=3,
        )

    async def increment_message_count(self, chat_id):
        return 4

    async def add_messages(self, chat_id, messages):
        self.saved_messages.append((chat_id, list(messages)))

    async def update_emotion(self, chat_id, emotion):
        self.updated_emotion = (chat_id, emotion)

    async def add_context_fact(self, chat_id, fact, max_facts=20):
        return None

    async def update_user_profile(self, chat_id, **fields):
        return None


class _DummyExportRag:
    async def search(self, ai_client, chat_id, query_text):
        return [{"text": "风格片段"}]

    def build_memory_message(self, results):
        return {"role": "system", "content": "风格片段"}


class _DummyVectorMemory:
    def __init__(self):
        self.inserted = []

    def search(self, query=None, n_results=5, filter_meta=None, query_embedding=None):
        return [{"text": "运行记忆", "distance": 0.2}]

    def add_text(self, text, metadata, id, embedding=None):
        self.inserted.append(
            {
                "text": text,
                "metadata": metadata,
                "id": id,
                "embedding": embedding,
            }
        )


def _fake_integrations(self):
    return {
        "AIMessage": _FakeMessage,
        "HumanMessage": _FakeMessage,
        "SystemMessage": _FakeMessage,
        "ChatOpenAI": _FakeChatOpenAI,
        "OpenAIEmbeddings": _FakeOpenAIEmbeddings,
        "START": "__start__",
        "END": "__end__",
        "StateGraph": _FakeStateGraph,
    }


@pytest.mark.asyncio
async def test_agent_runtime_prepare_request_aggregates_context(monkeypatch):
    monkeypatch.setattr(AgentRuntime, "_load_integrations", _fake_integrations)

    runtime = AgentRuntime(
        settings={
            "base_url": "https://example.com/v1",
            "api_key": "sk-test",
            "model": "test-model",
            "embedding_model": "embed-model",
        },
        bot_cfg={
            "system_prompt": "基础系统提示",
            "memory_context_limit": 5,
            "personalization_enabled": True,
            "emotion_detection_enabled": False,
            "rag_enabled": True,
            "remember_facts_enabled": True,
        },
        agent_cfg={"enabled": True, "streaming_enabled": True},
    )

    prepared = await runtime.prepare_request(
        event=SimpleNamespace(chat_name="张三", sender="用户", content="在吗"),
        chat_id="friend:张三",
        user_text="在吗",
        dependencies={
            "memory": _DummyMemory(),
            "export_rag": _DummyExportRag(),
            "vector_memory": _DummyVectorMemory(),
        },
    )

    assert "基础系统提示" in prepared.system_prompt
    assert any(item["content"] == "风格片段" for item in prepared.memory_context)
    assert any(item["content"].startswith("Relevant past memories") for item in prepared.memory_context)
    assert len(prepared.prompt_messages) >= 3


@pytest.mark.asyncio
async def test_agent_runtime_embedding_cache_hits(monkeypatch):
    monkeypatch.setattr(AgentRuntime, "_load_integrations", _fake_integrations)

    runtime = AgentRuntime(
        settings={
            "base_url": "https://example.com/v1",
            "api_key": "sk-test",
            "model": "test-model",
            "embedding_model": "embed-model",
        },
        bot_cfg={},
        agent_cfg={"enabled": True, "embedding_cache_ttl_sec": 300},
    )

    first = await runtime.get_embedding("hello")
    second = await runtime.get_embedding("hello")

    assert first == [5.0]
    assert second == [5.0]
    status = runtime.get_status()
    assert status["cache_stats"]["embedding_cache_hits"] == 1
    assert status["cache_stats"]["embedding_cache_misses"] == 1


@pytest.mark.asyncio
async def test_agent_runtime_finalize_request_persists_messages(monkeypatch):
    monkeypatch.setattr(AgentRuntime, "_load_integrations", _fake_integrations)

    memory = _DummyMemory()
    vector_memory = _DummyVectorMemory()
    runtime = AgentRuntime(
        settings={
            "base_url": "https://example.com/v1",
            "api_key": "sk-test",
            "model": "test-model",
            "embedding_model": "embed-model",
        },
        bot_cfg={
            "remember_facts_enabled": False,
        },
        agent_cfg={"enabled": True},
    )
    prepared = await runtime.prepare_request(
        event=SimpleNamespace(chat_name="李四", sender="用户", content="你好"),
        chat_id="friend:李四",
        user_text="你好",
        dependencies={
            "memory": memory,
            "export_rag": None,
            "vector_memory": vector_memory,
        },
    )

    await runtime.finalize_request(
        prepared,
        "收到",
        {"memory": memory, "export_rag": None, "vector_memory": vector_memory},
    )
    await asyncio.sleep(0)
    await runtime.close()

    assert memory.saved_messages[0][0] == "friend:李四"
    saved_roles = [item["role"] for item in memory.saved_messages[0][1]]
    assert saved_roles == ["user", "assistant"]
    assert len(vector_memory.inserted) == 2

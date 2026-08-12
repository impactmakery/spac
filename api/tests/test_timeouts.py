"""Every outbound call the worker makes must be bounded.

The worker is single-threaded and processes one job at a time. A call that
never returns does not merely delay one document — it stops the queue for
good, because the worker never reaches the top of its loop again. That also
disables the stalled-job recovery, which only runs at the start of a cycle:
the remedy for a hung worker is unreachable from inside a hung worker.

This happened in production. One document sat in 'running' for 45 minutes at
0% CPU while 345 others were finished, with nothing else being picked up.
"""

import pytest


def _openai_kwargs(monkeypatch, module, call):
    """Capture the kwargs the code passes to OpenAI()."""
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            raise RuntimeError("stop here — construction is all we are checking")

    monkeypatch.setattr("openai.OpenAI", FakeClient)
    with pytest.raises(RuntimeError):
        call()
    return captured


def test_the_embedding_client_cannot_block_the_worker_forever(monkeypatch):
    from app.core.config import get_settings
    from app.rag import embeddings

    monkeypatch.setattr(get_settings(), "embedding_api_key", "test-key")
    kwargs = _openai_kwargs(
        monkeypatch, embeddings, lambda: embeddings.ApiEmbeddings().embed(["text"])
    )
    assert kwargs["timeout"] == embeddings.EMBED_TIMEOUT_SECONDS
    assert kwargs["max_retries"] == embeddings.EMBED_MAX_RETRIES
    # the worst case a single call may cost the queue
    worst = embeddings.EMBED_TIMEOUT_SECONDS * (embeddings.EMBED_MAX_RETRIES + 1)
    assert worst < 10 * 60, "one embedding call could stall the queue for 10 minutes"


def test_the_chat_client_cannot_hold_a_request_open_forever(monkeypatch):
    from app.core.config import get_settings
    from app.rag import generation
    from app.rag.retrieval import RetrievedChunk

    monkeypatch.setattr(get_settings(), "llm_api_key", "test-key")
    import uuid

    chunk = RetrievedChunk(
        id=uuid.uuid4(), source_type="kb", source_id=uuid.uuid4(), content="c",
        visibility="global", municipality_id=None, department_id=None, similarity=0.9,
    )

    def call():
        list(generation.ApiGeneration().stream("q", [chunk], []))

    kwargs = _openai_kwargs(monkeypatch, generation, call)
    assert kwargs["timeout"] == generation.LLM_TIMEOUT_SECONDS
    assert kwargs["max_retries"] == generation.LLM_MAX_RETRIES


def test_the_storage_client_has_read_and_connect_timeouts(monkeypatch):
    """The worker downloads every file it indexes through this client."""
    from app.core.config import get_settings
    from app.services.storage import R2Provider

    # monkeypatch, not setattr: leaving credentials on the cached settings would
    # hand every later test the R2 provider, and the suite has written to the
    # production bucket that way before.
    settings = get_settings()
    for field, value in (
        ("r2_account_id", "acct"),
        ("r2_access_key_id", "key"),
        ("r2_secret_access_key", "secret"),
        ("r2_bucket", "bucket"),
    ):
        monkeypatch.setattr(settings, field, value)

    client = R2Provider()._client()
    config = client.meta.config
    assert config.connect_timeout is not None
    assert config.read_timeout is not None
    assert config.read_timeout <= 300, "a stalled download would stop the queue"

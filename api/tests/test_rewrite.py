"""Follow-up questions are searched as standalone ones.

Generation already sees the conversation, so an answer reads as if the
assistant is following along. Retrieval did not, which made "and the size
limit?" search for those words alone and find nothing — an assistant that
appeared to be listening and then claimed the material did not cover it.
"""

import pytest


def test_a_first_question_is_never_rewritten():
    """Nothing to resolve against, and a model call for it would be waste."""
    from app.rag.rewrite import needs_rewriting, standalone_question

    assert not needs_rewriting("What file types can I upload?", [])
    assert standalone_question("What file types can I upload?", []) == (
        "What file types can I upload?"
    )


def test_a_follow_up_with_history_is_worth_rewriting():
    from app.rag.rewrite import needs_rewriting

    history = [("user", "What file types can I upload?"), ("assistant", "PDF, DOCX…")]
    assert needs_rewriting("and the size limit?", history)


def test_an_enormous_question_is_left_alone():
    """A long question is already specific; rewriting risks losing detail."""
    from app.rag.rewrite import needs_rewriting

    history = [("user", "earlier"), ("assistant", "reply")]
    assert not needs_rewriting("x" * 900, history)


def test_the_original_question_survives_a_provider_failure(monkeypatch):
    """A rewrite failure must cost nothing: without it we are exactly where we
    were before the feature existed."""
    from app.rag import rewrite

    def explode(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(rewrite, "needs_rewriting", lambda q, h: True)
    monkeypatch.setattr("openai.OpenAI", explode)

    history = [("user", "What file types?"), ("assistant", "PDF, DOCX…")]
    assert rewrite.standalone_question("and the size limit?", history) == (
        "and the size limit?"
    )


@pytest.mark.parametrize("useless", ["", "   ", "x" * 2000])
def test_a_useless_rewrite_is_discarded(monkeypatch, useless):
    """A model that answers the question, refuses, or returns nothing has not
    given us something to search for."""
    from app.rag import rewrite

    class _Message:
        def __init__(self, content):
            self.content = content

    class _Choice:
        def __init__(self, content):
            self.message = _Message(content)

    class _Response:
        def __init__(self, content):
            self.choices = [_Choice(content)]

    class _Completions:
        def __init__(self, content):
            self._content = content

        def create(self, **kwargs):
            return _Response(self._content)

    class _Client:
        def __init__(self, content):
            self.chat = type("chat", (), {"completions": _Completions(content)})()

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_api_key", "test-key")

    history = [("user", "What file types?"), ("assistant", "PDF, DOCX…")]
    monkeypatch.setattr("openai.OpenAI", lambda **kw: _Client(useless))
    assert rewrite.standalone_question("and the size limit?", history) == (
        "and the size limit?"
    )


def test_a_good_rewrite_is_used(monkeypatch):
    from app.rag import rewrite

    class _Client:
        def __init__(self, content):
            completions = type("c", (), {"create": lambda self, **kw: type(
                "r", (), {"choices": [type("ch", (), {"message": type(
                    "m", (), {"content": content})()})()]})()})()
            self.chat = type("chat", (), {"completions": completions})()

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_api_key", "test-key")
    monkeypatch.setattr(
        "openai.OpenAI",
        lambda **kw: _Client('"What is the file upload size limit?"'),
    )

    history = [("user", "What file types?"), ("assistant", "PDF, DOCX…")]
    # surrounding quotation marks are stripped: models add them habitually
    assert rewrite.standalone_question("and the size limit?", history) == (
        "What is the file upload size limit?"
    )

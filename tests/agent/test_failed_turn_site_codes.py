"""Deterministic loop outcomes (context overflow, empty reply, persistence failure) end as
failed turns whose chat copy names the slash command to run, and whose ``failure_reason``
lets the desktop card pick a code-specific action instead of a blind Retry.
"""
from __future__ import annotations

from types import SimpleNamespace

from agent.error_surface import build_error_surface_from_result
from agent.turn_explainers import EMPTY_RESPONSE_EXPLANATION, TurnExplainersMixin
from agent.turn_failure_copy import exit_reason_failure, site_copy
from agent.turn_overflow import _Recovery


def _recovery():
    agent = SimpleNamespace(
        model="gpt-5", log_prefix="", _flush_status_buffer=lambda: None, _vprint=lambda *a, **k: None,
        _persist_session=lambda *a, **k: None,
    )
    return _Recovery(
        agent=agent, api_messages=[], system_message=None, effective_task_id="t", api_call_count=2,
        max_compression_attempts=3, messages=[], active_system_prompt=None, conversation_history=None,
        approx_tokens=200_000, compression_attempts=3,
    )


def test_overflow_exhaustion_is_non_retryable_context_overflow_with_slash_commands():
    verdict = _recovery().count_attempt()
    result = verdict.result
    assert result["failed"] is True and result["compression_exhausted"] is True
    assert result["failure_reason"] == "context_overflow" and result["failure_retryable"] is False
    text = result["final_response"]
    assert "/new" in text and "/compress" in text and "gpt-5" in text
    for jargon in ("compression attempts", "Context length exceeded", "safe threshold"):
        assert jargon not in text
    assert build_error_surface_from_result(result)["code"] == "context_overflow"


def test_payload_and_context_overflow_share_one_next_step():
    """413 and context-length exhaustion differ in cause text but never in what to do."""
    a = _recovery().count_attempt(payload_too_large=True).result["final_response"]
    b = _recovery().count_attempt().result["final_response"]
    assert ("/new" in a) and ("/compress" in a) and ("/new" in b) and ("/compress" in b)


def test_empty_response_exhaustion_is_a_failed_turn_with_one_text_everywhere():
    """One constant feeds the CLI explainer and the gateway '(empty)' rewrite; no surface
    asserts 'after processing tool results' or 'inspect the tool output above'."""
    assert exit_reason_failure("empty_response_exhausted") == ("empty_response", True)
    text = TurnExplainersMixin._format_turn_completion_explanation("empty_response_exhausted", model="llama3")
    assert text.startswith("⚠️ No reply: ") and "llama3" in text
    assert "/model" in text and "continue" in text
    assert "tool" not in text
    assert EMPTY_RESPONSE_EXPLANATION.format(model="llama3") in text


def test_persistence_failure_default_copy_is_actionable_and_profile_aware(monkeypatch):
    monkeypatch.setenv("HERMES_HOME", "/srv/hermes-profile")
    text = TurnExplainersMixin._format_turn_completion_explanation("session_persistence_failed", "replaced")
    assert "hermes gateway stop" in text and "hermes doctor" in text
    assert "~/.hermes" not in text and "/srv/hermes-profile" in text
    assert "manifest" not in text  # the runbook stays in logger.error at hermes_state


def test_reasoning_only_copy_gives_the_fix_before_the_scratchpad():
    text = site_copy("reasoning_only", model="r1", preview="the answer is 42")
    assert text.index("/reasoning low") < text.index("the answer is 42")
    assert "/model" in text

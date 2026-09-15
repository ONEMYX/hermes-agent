"""User-facing cron failure notices: plain words, the real output path, and the exact `hermes cron`
command to act on. Contract tests, not snapshots (root AGENTS.md).

The classifier is `agent.error_classifier.classify_api_error`; these tests pin what the copy table
does with its verdict, not the verdict itself.
"""

import re

import cron.scheduler as scheduler
from cron.scheduler import _compose_run_delivery, _summarize_cron_failure_for_delivery
from hermes_constants import display_hermes_home

JOB = {"name": "Morning brief", "id": "ab12cd34"}
_HTTP_LEAD = re.compile(r"failed: (HTTP|Error code:|provider )")


def _no_chain(monkeypatch):
    monkeypatch.setattr(scheduler, "load_config", lambda: {})
    monkeypatch.setattr(scheduler, "get_fallback_chain", lambda cfg: [])


def test_generic_failure_names_runs_and_pause_commands_and_the_real_output_dir():
    msg = _summarize_cron_failure_for_delivery(JOB, "[Errno 2] No such file or directory: '/x.py'")
    assert "/x.py" in msg  # the raw detail survives as the cause
    for cmd in ("hermes cron runs ab12cd34", "hermes cron run ab12cd34", "hermes cron pause ab12cd34"):
        assert f"`{cmd}`" in msg
    assert f"{display_hermes_home()}/cron/output/ab12cd34/" in msg
    assert "cron output" not in msg  # the unnamed internal location is gone


def test_auth_failure_points_at_login_and_a_retry_command(monkeypatch):
    _no_chain(monkeypatch)
    msg = _summarize_cron_failure_for_delivery(JOB, "Error code: 401 - Unauthorized")
    assert "/login" in msg and "`hermes login`" in msg
    assert "`hermes cron run ab12cd34`" in msg
    assert not _HTTP_LEAD.search(msg)
    assert "401" not in msg


def test_transient_provider_failures_never_lead_with_jargon(monkeypatch):
    _no_chain(monkeypatch)
    for err in ("Request timed out.", "HTTP 429: Too Many Requests"):
        msg = _summarize_cron_failure_for_delivery(JOB, err)
        assert not _HTTP_LEAD.search(msg), msg
        assert "fallback chain" not in msg.lower()
        assert "`hermes cron run ab12cd34`" in msg
        assert "`hermes cron runs ab12cd34`" in msg


def test_blocked_config_notice_says_it_did_not_run_and_will_self_heal():
    text, blocked, *_ = _compose_run_delivery(
        JOB, success=False, error="[blocked_config] provider credential missing: no key",
        final_response="", output_file=None)
    assert blocked is True
    assert "did not run" in text
    assert "provider credential missing: no key" in text
    assert "Nothing was charged" in text
    assert "`hermes cron doctor`" in text
    for jargon in ("configuration validation", "LLM call", "pre-dispatch"):
        assert jargon not in text

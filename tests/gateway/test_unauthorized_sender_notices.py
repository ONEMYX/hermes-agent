"""Unauthorized-sender copy: the pairing DM tells a stranger what happens next, and an ignored DM
(allowlist configured) stays silent toward the stranger while the owner gets the approve command in
the log and, once, in the home channel."""

import logging

import pytest

from gateway.config import HomeChannel, Platform
from gateway.pairing import PairingStore
from gateway.run import GatewayRunner
from gateway.run_inbound_unauthorized import (
    pairing_code_reply,
    record_silent_pairing_request,
    unauthorized_owner_hint,
)
from gateway.session import SessionSource
from tests.gateway.restart_test_helpers import make_restart_runner


def test_pairing_reply_states_expiry_owner_path_and_resend():
    reply = pairing_code_reply("telegram", "ABCD1234", "")
    assert "valid for 1 hour" in reply
    assert "`hermes pairing approve telegram ABCD1234`" in reply
    assert "send your message again" in reply
    assert "~" not in reply


def test_pairing_reply_pins_profile_in_approve_command():
    reply = pairing_code_reply("discord", "ZZZZ9999", "-p work ")
    assert "`hermes -p work pairing approve discord ZZZZ9999`" in reply


def test_silent_request_is_recorded_once_and_hint_names_it(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = PairingStore()
    first = record_silent_pairing_request(store, "telegram", "4242", "Ada")
    again = record_silent_pairing_request(store, "telegram", "4242", "Ada")
    assert first and first == again, "a repeat DM must not mint a second pending request"
    assert store.looks_like_request_id(first)

    hint = unauthorized_owner_hint(
        "telegram", "4242", "Ada", request_id=first, profile_arg="", hermes_home="~/.hermes")
    assert f"`hermes pairing approve telegram {first}`" in hint
    assert "TELEGRAM_ALLOWED_USERS" in hint and "~/.hermes/.env" in hint


@pytest.mark.asyncio
async def test_ignored_dm_sends_nothing_to_stranger_and_notifies_owner_once(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    runner, adapter = make_restart_runner()
    runner.pairing_store = PairingStore()
    runner.pairing_stores = {}
    runner.config.platforms[Platform.TELEGRAM].home_channel = HomeChannel(
        platform=Platform.TELEGRAM, chat_id="home-1", name="Ops")
    runner._hm_report_ignored_dm = GatewayRunner._hm_report_ignored_dm.__get__(runner, GatewayRunner)
    stranger = SessionSource(platform=Platform.TELEGRAM, chat_id="dm-777", user_id="777", user_name="Eve", chat_type="dm")

    with caplog.at_level(logging.WARNING, logger="gateway.run"):
        await runner._hm_report_ignored_dm(stranger)
        await runner._hm_report_ignored_dm(stranger)

    chats = [chat_id for chat_id, _msg, _meta in adapter.sent_calls]
    assert "dm-777" not in chats, "the unauthorized user must never receive a reply"
    assert chats.count("home-1") == 1, "the owner is told once per sender, not per message"
    assert "hermes pairing approve telegram" in adapter.sent_calls[0][1]
    assert any("hermes pairing approve telegram" in r.getMessage() for r in caplog.records)

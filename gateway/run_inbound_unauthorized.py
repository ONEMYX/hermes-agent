"""Copy and owner-side signalling for unauthorized inbound senders.

Two audiences, two rules:

* The **stranger** gets either a pairing code (behaviour ``pair``) or nothing at all (behaviour
  ``ignore``: an allowlist is configured, so any reply would leak that the bot exists).
* The **owner** is the one who can fix a mis-typed allowlist or approve a request, so an ignored DM
  is still recorded as a pending pairing request (server-side only; the code is discarded, nothing
  is sent), logged at WARNING with the exact ``hermes pairing approve`` command, and surfaced once
  per (platform, user) per gateway process in the platform's home channel when one is configured.
"""

from __future__ import annotations

import logging

from gateway.pairing import CODE_TTL_SECONDS, _allowlist_env_for_platform

logger = logging.getLogger("gateway.run")


def pairing_profile_arg(pairing_store) -> str:
    """``-p <profile> `` when the store belongs to a non-default profile, else ``""``."""
    store_profile = getattr(pairing_store, "profile", None)
    if isinstance(store_profile, str) and store_profile and store_profile != "default":
        return f"-p {store_profile} "
    return ""


def pairing_code_reply(platform_name: str, code: str, profile_arg: str = "") -> str:
    """The DM a first-time sender receives: what happened, how long the code lives, what to do
    whether they are the owner or a guest, and that they must message again after approval."""
    hours = max(1, CODE_TTL_SECONDS // 3600)
    validity = f"{hours} hour" if hours == 1 else f"{hours} hours"
    approve_cmd = f"hermes {profile_arg}pairing approve {platform_name} {code}"
    return (
        "Hi! I don't recognize you yet, so I can't reply until the person running this bot "
        "approves you.\n\n"
        f"Your pairing code: `{code}` (valid for {validity})\n\n"
        f"If you run this bot, open a terminal and run: `{approve_cmd}`. "
        "Otherwise send that command to the bot owner. After approval, send your message again."
    )


PAIRING_RATE_LIMITED_REPLY = (
    "Too many pairing requests right now. Wait a few minutes, then send your message again.")


def record_silent_pairing_request(pairing_store, platform_name: str, user_id: str, user_name: str) -> str | None:
    """Create (or reuse) a pending request for an ignored DM sender without telling them; returns
    the request id the owner can approve (``hermes pairing approve <platform> <request-id>``), or
    None when the store is rate-limited / full / locked out and no earlier request exists."""
    def _mine():
        rows = [p for p in pairing_store.list_pending(platform_name)
                if str(p.get("user_id")) == str(user_id) and p.get("request_id")]
        return rows[-1]["request_id"] if rows else None

    existing = _mine()
    if existing:
        return existing
    if pairing_store.generate_code(platform_name, user_id, user_name or "") is None:
        return None
    return _mine()


def unauthorized_owner_hint(
    platform_name: str, user_id: str, user_name: str = "", *, request_id: str | None,
    profile_arg: str = "", hermes_home: str,
) -> str:
    """One-line hint for the owner (log + home channel): who was dropped and how to let them in."""
    who = f"{user_name} ({user_id})" if user_name else str(user_id)
    approve = (
        f"run `hermes {profile_arg}pairing approve {platform_name} {request_id}` on the host"
        if request_id else f"run `hermes {profile_arg}pairing list` on the host to approve them"
    )
    env_var = _allowlist_env_for_platform(platform_name)
    allowlist = (
        f", or add the ID to {env_var} in {hermes_home}/.env and restart the gateway"
        if env_var else ""
    )
    return (
        f"Dropped a message from unrecognized {platform_name} user {who}. "
        f"If that is you or someone you trust, {approve}{allowlist}."
    )


class UnauthorizedOwnerNotifier:
    """Tells the owner's home channel about the first drop of each unrecognized DM sender.

    One notice per (platform, user_id) per gateway process: the first drop is the useful signal (an
    owner who typo'd their own ID); repeats would only let a stranger spam the home channel.
    """

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()

    def first_time(self, platform_name: str, user_id: str) -> bool:
        key = (platform_name, str(user_id))
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    async def notify(self, runner, source, hint: str) -> None:
        """Best-effort post to the source platform's home channel; silent when none is configured."""
        for platform, _cfg, home, transport in runner._home_channel_transports():
            if platform != source.platform:
                continue
            if str(home.chat_id) == str(source.chat_id):
                # The stranger's DM *is* the home channel (misconfiguration); posting there would
                # answer the unauthorized user, which the ignore behaviour exists to prevent.
                return
            await runner._send_home_channel_message(
                platform, home, transport, f"⚠️ {hint}", "unauthorized-sender notice failed for %s:%s: %s",
            )
            return

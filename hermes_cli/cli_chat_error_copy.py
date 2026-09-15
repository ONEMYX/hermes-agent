"""Plain-language copy for chat-turn failures shown in the CLI response panel.

The chat panel used to echo ``Error: HTTP 401: Invalid API key`` as the assistant's answer. These
helpers map the classifier verdict (``agent/error_classifier.py``) to WHAT happened + WHAT TO DO,
and demote the raw provider text to a ``Details:`` line.
"""

from __future__ import annotations

_SUMMARY_LIMIT = 120

# FailoverReason.value -> plain copy. ``{provider}`` / ``{model}`` are filled at render time.
_REASON_COPY: dict[str, str] = {
    "auth": "Your {provider} key was rejected. Run `hermes model` to re-enter it.",
    "auth_permanent": "Your {provider} key was rejected. Run `hermes model` to re-enter it.",
    "billing": "Your {provider} account is out of credit. Top up at the provider, or run /model to switch.",
    "model_not_found": "'{model}' isn't available on {provider}. Run /model to pick a valid model.",
    "rate_limit": "Rate limited by {provider}; wait a minute or /model to switch.",
    "upstream_rate_limit": "Rate limited by {provider}; wait a minute or /model to switch.",
}
_UNKNOWN_COPY = "The model request failed. Run /model to switch or `hermes doctor` to check the setup."


def _short(text: str, limit: int = _SUMMARY_LIMIT) -> str:
    first = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


def chat_error_response(error: Exception | str, *, provider: str = "", model: str = "") -> str:
    """Two-line panel text: plain sentence with the fix command, then ``Details: <raw>``."""
    from agent.error_classifier import classify_api_error

    exc = error if isinstance(error, Exception) else Exception(str(error))
    verdict = classify_api_error(exc, provider=provider or "", model=model or "")
    copy = _REASON_COPY.get(verdict.reason.value, _UNKNOWN_COPY)
    lead = copy.format(provider=provider or "the provider", model=model or "the current model")
    return f"{lead}\nDetails: {_short(str(error), 300)}"


def agent_init_failure_message(error: BaseException) -> str:
    """Copy for a failed AIAgent build on first message: the user's turn was dropped."""
    return (
        f"Hermes couldn't start the model connection: {_short(str(error)) or type(error).__name__}. "
        "Your message was not sent. Run `hermes doctor` to check the setup, "
        "or /model to pick a different provider."
    )

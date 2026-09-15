"""Plain-language contracts for hermes_state user-facing errors (CLI UX message campaign, cluster D)."""

import hermes_state
from hermes_state import SessionResumeTooLargeError, format_session_db_unavailable


def test_resume_too_large_names_export_and_config_commands():
    text = str(SessionResumeTooLargeError(4312, 4000))
    assert "4312" in text and "4000" in text
    assert "hermes sessions export" in text
    assert "hermes config set sessions.max_resume_messages 0" in text
    for jargon in ("lineage", "guard", "safe resume limit"):
        assert jargon not in text


def test_resume_too_large_keeps_structured_fields():
    exc = SessionResumeTooLargeError(20_001, 20_000, scope="in its tip segment")
    assert (exc.message_count, exc.limit) == (20_001, 20_000)
    assert isinstance(exc, ValueError)


def test_db_unavailable_points_to_doctor_without_sqlite_internals():
    hermes_state._set_last_init_error("OperationalError: locking protocol")
    try:
        text = format_session_db_unavailable()
    finally:
        hermes_state._set_last_init_error(None)
    lead, *rest = text.splitlines()
    assert "hermes doctor" in lead
    assert "session history" in lead
    for internal in ("sqlite.org", "WAL", "NFS/SMB/FUSE/ZFS"):
        assert internal not in lead
    assert rest and rest[0].startswith("Details: ") and "locking protocol" in rest[0]


def test_db_unavailable_without_cause_still_names_doctor():
    hermes_state._set_last_init_error(None)
    text = format_session_db_unavailable()
    assert "hermes doctor" in text
    assert "Details:" not in text

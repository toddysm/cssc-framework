from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import httpx
import pytest
import yaml

from cssc_common import MirrorHistoryEntry, Tag
from mirror_history_e2e import Fixture, cleanup, serve, validate_dashboard, validate_state

DIGEST = "sha256:" + "a" * 64
FIXTURE = Fixture("toddysm", "123", "1")


def entry(force: bool = False) -> MirrorHistoryEntry:
    return MirrorHistoryEntry(
        source_tag="upstream",
        source_digest=DIGEST,
        dest_tag="image",
        synced_at=datetime(2026, 10, 27, tzinfo=timezone.utc).isoformat(),
        run_url="https://github.com/toddysm/cssc-framework/actions/runs/123",
        run_id="123",
        run_attempt="1",
        force=force,
    )


def initial():
    return validate_state(
        "initial", FIXTURE,
        [Tag(tag="image", digest=DIGEST), Tag(tag="mirror-history")],
        [Tag(tag="upstream", digest=DIGEST)],
        [entry()], DIGEST, None, "true", "false",
    )


@pytest.mark.parametrize("owner,run_id,attempt", [
    ("toddysm/normal-image", "123", "1"),
    ("toddysm", "../python", "1"),
    ("toddysm", "123", "0"),
    ("toddysm", "123", "1/../../python"),
    ("", "123", "1"),
])
def test_fixture_rejects_unsafe_coordinates(owner, run_id, attempt):
    with pytest.raises(ValueError):
        Fixture(owner, run_id, attempt)


def test_complete_lifecycle():
    snapshot = initial()
    for phase in ("promoted", "skipped"):
        validate_state(
            phase, FIXTURE, [Tag(tag="mirror-history")],
            [Tag(tag="upstream", digest=DIGEST), Tag(tag="image", digest=DIGEST)],
            snapshot.entries, DIGEST, snapshot,
            "false" if phase == "skipped" else None,
            "true" if phase == "skipped" else None,
        )
    forced = validate_state(
        "forced", FIXTURE,
        [Tag(tag="image", digest=DIGEST), Tag(tag="mirror-history")],
        [Tag(tag="upstream", digest=DIGEST), Tag(tag="image", digest=DIGEST)],
        [entry(), entry(force=True)], DIGEST, snapshot, "true", "false",
    )
    assert len(forced.entries) == 2


@pytest.mark.parametrize("tags,history,copied,skipped", [
    ([Tag(tag="mirror-history"), Tag(tag="image", digest=DIGEST)], [entry()], "false", "true"),
    ([Tag(tag="mirror-history")], [entry(), entry()], "false", "true"),
    ([Tag(tag="mirror-history")], [entry()], "true", "false"),
    ([], [entry()], "false", "true"),
])
def test_skip_requires_no_copy_no_new_history_and_surviving_package(tags, history, copied, skipped):
    with pytest.raises(AssertionError):
        validate_state(
            "skipped", FIXTURE, tags,
            [Tag(tag="upstream", digest=DIGEST), Tag(tag="image", digest=DIGEST)],
            history, DIGEST, initial(), copied, skipped,
        )


def test_force_cannot_rewrite_history():
    with pytest.raises(AssertionError):
        validate_state(
            "forced", FIXTURE,
            [Tag(tag="mirror-history"), Tag(tag="image", digest=DIGEST)],
            [Tag(tag="upstream", digest=DIGEST), Tag(tag="image", digest=DIGEST)],
            [entry(force=True)], DIGEST, initial(), "true", "false",
        )


def test_dashboard_checks_the_fixture_card_not_another_image():
    snapshot = initial()
    card = (
        f'<article class="image-card"><code>{FIXTURE.quarantine}</code>'
        f'<span>0 tag(s)</span><span>not in quarantine</span>'
        f'Synchronized (1) {DIGEST[:19]} {snapshot.entries[0].synced_at}'
        f' <a href="{snapshot.entries[0].run_url}">run</a></article>'
    )
    assert FIXTURE.quarantine in validate_dashboard(card, FIXTURE, snapshot, True)
    with pytest.raises(AssertionError):
        validate_dashboard(card.replace(FIXTURE.quarantine, "quarantine/python"), FIXTURE, snapshot, True)
    with pytest.raises(AssertionError):
        validate_dashboard(card.replace(">not in quarantine<", ">waiting<"), FIXTURE, snapshot, True)


def test_cleanup_only_deletes_the_two_computed_fixture_packages():
    deleted = []

    def handler(request):
        path = request.url.path
        if path == "/users/toddysm":
            return httpx.Response(200, json={"type": "User"})
        if path == "/user":
            return httpx.Response(200, json={"login": "toddysm"})
        assert "mirror-history-e2e-123-1" in path
        if request.method == "DELETE":
            deleted.append(path)
            return httpx.Response(204)
        return httpx.Response(404 if path in deleted else 200, json={})

    with httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler)) as client:
        cleanup(FIXTURE, client)
    assert len(deleted) == 2
    assert all("quarantine/python" not in path for path in deleted)


def test_cleanup_does_not_hide_authentication_failure():
    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(lambda request: httpx.Response(403)),
    ) as client, pytest.raises(httpx.HTTPStatusError):
        cleanup(FIXTURE, client)


def test_cleanup_rejects_another_users_token():
    def handler(request):
        body = {"type": "User"} if request.url.path == "/users/toddysm" else {"login": "someone-else"}
        assert request.method == "GET"
        return httpx.Response(200, json=body)

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as client, pytest.raises(ValueError, match="fixture owner"):
        cleanup(FIXTURE, client)


def test_cleanup_fails_when_a_deleted_package_remains_visible():
    def handler(request):
        if request.url.path == "/users/toddysm":
            return httpx.Response(200, json={"type": "User"})
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "toddysm"})
        return httpx.Response(204 if request.method == "DELETE" else 200, json={})

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as client, patch("mirror_history_e2e.time") as clock:
        clock.monotonic.side_effect = [0, 31]
        with pytest.raises(RuntimeError, match="still exists after deletion"):
            cleanup(FIXTURE, client)
        clock.sleep.assert_not_called()


def test_startup_errors_redact_server_credentials(tmp_path, capsys):
    (tmp_path / "broken_server.py").write_text(
        "import os\nraise RuntimeError(os.environ['GITHUB_TOKEN'])\n"
    )
    with pytest.raises(RuntimeError, match="exited during startup"):
        with serve("broken_server:app", {
            "PYTHONPATH": str(tmp_path),
            "GITHUB_TOKEN": "test-only-value",
        }):
            pytest.fail("A failed service must not become ready")
    output = capsys.readouterr().err
    assert "[REDACTED]" in output
    assert "test-only-value" not in output


def test_cli_cannot_silently_disable_acceptance_assertions():
    result = subprocess.run(
        [sys.executable, "-O", str(Path(__file__).with_name("mirror_history_e2e.py")), "coordinates"],
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "assertions are required" in result.stderr


def test_actual_http_service_becomes_ready_and_stops():
    with serve("packages_service.app:app", {}) as url:
        assert httpx.get(f"{url}/healthz").json() == {"status": "ok"}
    with pytest.raises(httpx.ConnectError):
        httpx.get(f"{url}/healthz", timeout=1)


def test_workflow_observability_preserves_existing_artifact_default():
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.load(
        (root / ".github/workflows/_mirror-image.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    call = workflow["on"]["workflow_call"]
    assert call["inputs"]["graph_events_artifact_name"]["default"] == "graph-events"
    assert set(call["outputs"]) == {"copied", "skipped", "digest"}
    live = yaml.load(
        (root / ".github/workflows/validate-mirror-history.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    assert live["concurrency"]["cancel-in-progress"] == "false"
    assert live["jobs"]["cleanup"]["if"].startswith("${{ always()")
    assert live["jobs"]["promote"]["with"]["enable_approval"] == "false"

from datetime import datetime, timezone
import json
from pathlib import Path
import os
import subprocess
import sys
from unittest.mock import patch

import httpx
import pytest
import yaml

from cssc_common import MirrorHistoryEntry, Tag
from mirror_history_e2e import (
    Fixture, cleanup, redact_diagnostics, serve, validate_dashboard, validate_state, wait_for_visibility,
)

DIGEST = "sha256:" + "a" * 64
HISTORY_DIGEST = "sha256:" + "b" * 64
REFERRER_DIGEST = "sha256:" + "c" * 64
FORCED_HISTORY_DIGEST = "sha256:" + "d" * 64
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
        [Tag(tag="image", digest=DIGEST), Tag(tag="mirror-history", digest=HISTORY_DIGEST)],
        [Tag(tag="upstream", digest=DIGEST)],
        [entry()], DIGEST, None, "true", "false", {DIGEST, HISTORY_DIGEST, REFERRER_DIGEST},
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
            phase, FIXTURE, [Tag(tag="mirror-history", digest=HISTORY_DIGEST)],
            [Tag(tag="upstream", digest=DIGEST), Tag(tag="image", digest=DIGEST)],
            snapshot.entries, DIGEST, snapshot,
            "false" if phase == "skipped" else None,
            "true" if phase == "skipped" else None,
            {HISTORY_DIGEST},
        )
    forced = validate_state(
        "forced", FIXTURE,
        [Tag(tag="image", digest=DIGEST), Tag(tag="mirror-history", digest=FORCED_HISTORY_DIGEST)],
        [Tag(tag="upstream", digest=DIGEST), Tag(tag="image", digest=DIGEST)],
        [entry(), entry(force=True)], DIGEST, snapshot, "true", "false",
        {DIGEST, HISTORY_DIGEST, FORCED_HISTORY_DIGEST, REFERRER_DIGEST},
    )
    assert len(forced.entries) == 2


@pytest.mark.parametrize("tags,history,copied,skipped", [
    ([Tag(tag="mirror-history", digest=HISTORY_DIGEST), Tag(tag="image", digest=DIGEST)], [entry()], "false", "true"),
    ([Tag(tag="mirror-history", digest=HISTORY_DIGEST)], [entry(), entry()], "false", "true"),
    ([Tag(tag="mirror-history", digest=HISTORY_DIGEST)], [entry()], "true", "false"),
    ([], [entry()], "false", "true"),
])
def test_skip_requires_no_copy_no_new_history_and_surviving_package(tags, history, copied, skipped):
    with pytest.raises(AssertionError):
        validate_state(
            "skipped", FIXTURE, tags,
            [Tag(tag="upstream", digest=DIGEST), Tag(tag="image", digest=DIGEST)],
            history, DIGEST, initial(), copied, skipped, {HISTORY_DIGEST},
        )


def test_force_cannot_rewrite_history():
    with pytest.raises(AssertionError):
        validate_state(
            "forced", FIXTURE,
            [Tag(tag="mirror-history", digest=FORCED_HISTORY_DIGEST), Tag(tag="image", digest=DIGEST)],
            [Tag(tag="upstream", digest=DIGEST), Tag(tag="image", digest=DIGEST)],
            [entry(force=True)], DIGEST, initial(), "true", "false",
            {DIGEST, HISTORY_DIGEST, FORCED_HISTORY_DIGEST, REFERRER_DIGEST},
        )


def test_force_rerun_preserves_creation_identity_and_records_execution_attempt():
    forced = entry(force=True).model_copy(update={"run_attempt": "2"})
    snapshot = validate_state(
        "forced", FIXTURE,
        [Tag(tag="image", digest=DIGEST), Tag(tag="mirror-history", digest=FORCED_HISTORY_DIGEST)],
        [Tag(tag="upstream", digest=DIGEST), Tag(tag="image", digest=DIGEST)],
        [entry(), forced], DIGEST, initial(), "true", "false",
        {DIGEST, HISTORY_DIGEST, FORCED_HISTORY_DIGEST, REFERRER_DIGEST},
    )
    assert snapshot.attempt == "1" and snapshot.entries[-1].run_attempt == "2"


def test_explicit_creation_attempt_survives_a_partial_rerun(tmp_path):
    output = tmp_path / "outputs"
    subprocess.run(
        [
            sys.executable, str(Path(__file__).with_name("mirror_history_e2e.py")),
            "coordinates", "--owner", "toddysm", "--run-id", "123", "--attempt", "1",
        ],
        env={**os.environ, "GITHUB_RUN_ATTEMPT": "2", "GITHUB_OUTPUT": str(output)},
        check=True,
    )
    text = output.read_text()
    assert "fixture_attempt=1\n" in text
    assert "mirror-history-e2e-123-1/image" in text
    assert "mirror-history-e2e-123-2" not in text


def test_untagged_referrers_cannot_survive_promotion():
    with pytest.raises(AssertionError, match="Untagged image/referrer"):
        validate_state(
            "promoted", FIXTURE, [Tag(tag="mirror-history", digest=HISTORY_DIGEST)],
            [Tag(tag="upstream", digest=DIGEST), Tag(tag="image", digest=DIGEST)],
            [entry()], DIGEST, initial(), None, None, {HISTORY_DIGEST, REFERRER_DIGEST},
        )


@pytest.mark.parametrize("status", [404, 429, 500, 502, 503, 504])
def test_visibility_poll_retries_transient_http_errors(status):
    attempts = 0

    def observe():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            httpx.Response(status, request=httpx.Request("GET", "https://api.github.com/fixture")).raise_for_status()
        return initial(), "card"

    with patch("mirror_history_e2e.time.sleep"):
        snapshot, card = wait_for_visibility(observe)
    assert attempts == 2 and card == "card" and snapshot.digest == DIGEST


@pytest.mark.parametrize("status", [401, 403])
def test_visibility_poll_does_not_hide_authentication_failure(status):
    def observe():
        httpx.Response(status, request=httpx.Request("GET", "https://api.github.com/fixture")).raise_for_status()
        return initial(), "card"

    with patch("mirror_history_e2e.time.sleep") as sleep, pytest.raises(httpx.HTTPStatusError):
        wait_for_visibility(observe)
    sleep.assert_not_called()


def test_visibility_poll_has_a_real_deadline():
    def observe():
        raise AssertionError("not visible")

    with patch("mirror_history_e2e.time") as clock:
        clock.monotonic.side_effect = [0, 91]
        with pytest.raises(AssertionError, match="not visible"):
            wait_for_visibility(observe)
        clock.sleep.assert_not_called()


def test_diagnostics_remove_signed_download_queries_and_tokens():
    text = "token=test-only-value redirect='https://cdn.example.test/blob?sig=example-signature&hmac=example-hmac'"
    redacted = redact_diagnostics(text, {"GITHUB_TOKEN": "test-only-value"})
    assert "test-only-value" not in redacted
    assert "example-signature" not in redacted and "example-hmac" not in redacted
    assert "https://cdn.example.test/blob?[REDACTED]" in redacted


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
        clock.monotonic.side_effect = [0, 31, 31, 62]
        with pytest.raises(RuntimeError, match="still exists after deletion"):
            cleanup(FIXTURE, client)
        clock.sleep.assert_not_called()


def test_cleanup_still_deletes_golden_after_quarantine_deletion_fails():
    attempted = []

    def handler(request):
        path = request.url.path
        if path == "/users/toddysm":
            return httpx.Response(200, json={"type": "User"})
        if path == "/user":
            return httpx.Response(200, json={"login": "toddysm"})
        if request.method == "DELETE":
            attempted.append(path)
            return httpx.Response(403 if "/quarantine/" in path else 204)
        return httpx.Response(404 if path in attempted and "/golden/" in path else 200, json={})

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as client, pytest.raises(RuntimeError, match="cleanup incomplete"):
        cleanup(FIXTURE, client)
    assert len(attempted) == 2
    assert "/quarantine/" in attempted[0] and "/golden/" in attempted[1]


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


@pytest.mark.parametrize("exclude,expected", [
    ("true", ["image"]),
    ("false", ["image", "sha256-subject"]),
])
def test_tag_enumeration_filters_metadata_without_losing_image_tags(tmp_path, exclude, expected):
    root = Path(__file__).resolve().parents[2]
    action = yaml.load(
        (root / ".github/actions/enumerate-tags/action.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    crane = tmp_path / "crane"
    crane.write_text("#!/bin/sh\nprintf '%s\\n' image mirror-history sha256-subject\n")
    crane.chmod(0o755)
    output = tmp_path / "outputs"
    subprocess.run(
        ["bash", "-c", action["runs"]["steps"][0]["run"]],
        env={
            **os.environ,
            "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            "TMPDIR": str(tmp_path),
            "GITHUB_OUTPUT": str(output),
            "REPOSITORY": "ghcr.io/toddysm/quarantine/test-fixture",
            "EXCLUDE_REFERRER_TAGS": exclude,
        },
        check=True,
    )
    results = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert json.loads(results["tags-json"]) == expected
    assert results["has-tags"] == "true"


def test_workflow_observability_preserves_existing_artifact_default():
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.load(
        (root / ".github/workflows/_mirror-image.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    call = workflow["on"]["workflow_call"]
    assert call["inputs"]["graph_events_artifact_name"]["default"] == "graph-events"
    assert set(call["outputs"]) == {"copied", "skipped", "digest", "run_attempt"}
    live = yaml.load(
        (root / ".github/workflows/validate-mirror-history.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    assert live["concurrency"]["cancel-in-progress"] == "false"
    assert live["jobs"]["cleanup"]["if"].startswith("${{ always()")
    assert live["jobs"]["promote"]["with"]["enable_approval"] == "false"
    for name in ("_promote-from-quarantine.yml", "_promote-from-quarantine-sbom.yml"):
        promotion = yaml.load(
            (root / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader,
        )
        enumeration = next(
            step for step in promotion["jobs"]["enumerate"]["steps"]
            if step.get("uses") == "./.github/actions/enumerate-tags"
        )
        assert enumeration["with"]["exclude-referrer-tags"] == "true"
    assert live["jobs"]["prepare"]["outputs"]["fixture_attempt"] == "${{ steps.paths.outputs.fixture_attempt }}"
    cleanup_step = live["jobs"]["cleanup"]["steps"][-1]
    assert cleanup_step["env"]["FIXTURE_ATTEMPT"] == "${{ needs.prepare.outputs.fixture_attempt || github.run_attempt }}"
    for name in ("verify-initial", "verify-promoted", "verify-skipped", "verify-forced"):
        steps = live["jobs"][name]["steps"]
        assertion = next(step for step in steps if "FIXTURE_ATTEMPT" in step.get("env", {}))
        assert '--attempt "${FIXTURE_ATTEMPT}"' in assertion["run"]
        for step in steps:
            if "download-artifact@" in step.get("uses", ""):
                assert step["with"]["name"] == "${{ needs.verify-initial.outputs.evidence_artifact }}"
    for name in ("verify-initial", "verify-forced"):
        assertion = next(step for step in live["jobs"][name]["steps"] if "MIRROR_ATTEMPT" in step.get("env", {}))
        assert '--execution-attempt "${MIRROR_ATTEMPT}"' in assertion["run"]

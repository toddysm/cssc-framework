"""Live mirror-history assertions and cleanup for disposable GHCR fixtures."""

from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterator
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field, TypeAdapter

from cssc_common import GitHubClient, MirrorHistoryEntry, MirroredImage, Tag

IMAGE_TAG = "image"
SOURCE_TAG = "upstream"
HISTORY_TAG = "mirror-history"


@dataclass(frozen=True)
class Fixture:
    owner: str
    run_id: str
    attempt: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?", self.owner):
            raise ValueError("A lowercase GitHub owner is required")
        if not all(re.fullmatch(r"[1-9][0-9]*", value) for value in (self.run_id, self.attempt)):
            raise ValueError("Run ID and attempt must be positive integers")

    @property
    def namespace(self) -> str:
        return f"quarantine/mirror-history-e2e-{self.run_id}-{self.attempt}"

    @property
    def quarantine(self) -> str:
        return f"{self.namespace}/image"

    @property
    def golden(self) -> str:
        return f"golden/mirror-history-e2e-{self.run_id}-{self.attempt}/image"

    def coordinates(self) -> dict[str, str]:
        return {
            "fixture_attempt": self.attempt,
            "namespace": self.namespace,
            "quarantine": self.quarantine,
            "golden": self.golden,
            "quarantine_image": f"ghcr.io/{self.owner}/{self.quarantine}",
            "golden_image": f"ghcr.io/{self.owner}/{self.golden}",
        }


class Snapshot(BaseModel):
    owner: str
    run_id: str
    attempt: str
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    history_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    quarantine_versions: list[str]
    entries: list[MirrorHistoryEntry]


class PackageVersion(BaseModel):
    name: str


def redact_diagnostics(text: str, environment: dict[str, str]) -> str:
    for key in ("GITHUB_TOKEN", "GHCR_DELETE_TOKEN"):
        token = environment.get(key) or os.environ.get(key)
        if token:
            text = text.replace(token, "[REDACTED]")
    return re.sub(r"(https?://[^\s'\"?]+)\?[^\s'\"]+", r"\1?[REDACTED]", text)


@contextmanager
def serve(module: str, environment: dict[str, str]) -> Iterator[str]:
    with socket.socket() as listener, tempfile.TemporaryFile(mode="w+") as log:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        # Passing the bound socket avoids a free-port race between processes.
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", module, "--fd", str(listener.fileno())],
            env={**os.environ, **environment},
            pass_fds=(listener.fileno(),),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            with httpx.Client(timeout=1) as client:
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"{module} exited during startup ({process.returncode})")
                    try:
                        response = client.get(f"{url}/healthz")
                        response.raise_for_status()
                        break
                    except httpx.TransportError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError(f"{module} did not become ready at {url}")
                        time.sleep(0.1)
            yield url
        finally:
            failed = sys.exc_info()[0] is not None
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if failed:
                log.seek(0)
                detail = redact_diagnostics(log.read(), environment)
                if detail:
                    print(f"{module} log:\n{detail}", file=sys.stderr)


def validate_state(
    phase: str,
    fixture: Fixture,
    quarantine_tags: list[Tag],
    golden_tags: list[Tag],
    history: list[MirrorHistoryEntry],
    digest: str,
    expected: Snapshot | None,
    copied: str | None,
    skipped: str | None,
    quarantine_versions: set[str],
) -> Snapshot:
    assert history, "History must exist after the initial mirror"
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest), "Missing or invalid workflow digest"
    quarantine = {tag.tag: tag.digest for tag in quarantine_tags}
    golden = {tag.tag: tag.digest for tag in golden_tags}
    assert HISTORY_TAG in quarantine, "The standalone history tag must survive"
    history_digest = quarantine[HISTORY_TAG]
    assert isinstance(history_digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", history_digest)
    assert golden.get(SOURCE_TAG) == digest, "The controlled upstream image must remain unchanged"
    times = []
    for entry in history:
        assert entry.source_tag == SOURCE_TAG
        assert entry.dest_tag == IMAGE_TAG
        assert entry.source_digest == digest
        assert entry.run_id == fixture.run_id
        assert entry.run_attempt and re.fullmatch(r"[1-9][0-9]*", entry.run_attempt)
        assert int(entry.run_attempt) >= int(fixture.attempt)
        assert entry.synced_at, "Every entry needs a timestamp"
        timestamp = datetime.fromisoformat(entry.synced_at.replace("Z", "+00:00"))
        assert timestamp.utcoffset() is not None, "History timestamps must include a timezone"
        times.append(timestamp)
        assert entry.run_url == (
            f"https://github.com/{fixture.owner}/cssc-framework/actions/runs/{fixture.run_id}"
        )
    assert times == sorted(times), "History must remain chronological"

    if phase == "initial":
        assert expected is None
        assert copied == "true" and skipped == "false"
        assert quarantine.get(IMAGE_TAG) == digest
        assert IMAGE_TAG not in golden, "Promotion must not have happened yet"
        assert len(history) == 1 and history[0].force is False
        assert {digest, history_digest}.issubset(quarantine_versions)
        assert quarantine_versions - {digest, history_digest}, "An initial referrer must exist to test its deletion"
    elif phase in {"promoted", "skipped", "forced"}:
        assert expected is not None, "The initial snapshot is required"
        assert (expected.owner, expected.run_id, expected.attempt) == (
            fixture.owner, fixture.run_id, fixture.attempt
        ), "The snapshot belongs to a different fixture"
        assert digest == expected.digest
        assert golden.get(IMAGE_TAG) == digest, "Promotion must preserve the digest"
        if phase == "forced":
            assert copied == "true" and skipped == "false"
            assert quarantine.get(IMAGE_TAG) == digest
            assert history[:-1] == expected.entries, "Force must not rewrite earlier history"
            assert len(history) == len(expected.entries) + 1 and history[-1].force is True
            assert history_digest != expected.history_digest, "Appended history must be persisted as a new artifact"
        else:
            assert set(quarantine) == {HISTORY_TAG}, "Only history may remain after deletion"
            assert quarantine_versions == {history_digest}, (
                "Untagged image/referrer versions must also be deleted; remaining: "
                f"{sorted(quarantine_versions - {history_digest})}"
            )
            assert history_digest == expected.history_digest
            assert history == expected.entries, "Promotion and history skips must not append entries"
            if phase == "skipped":
                assert copied == "false" and skipped == "true", "The actual workflow must skip"
    else:
        raise ValueError(f"Unknown validation phase: {phase}")

    return Snapshot(
        owner=fixture.owner,
        run_id=fixture.run_id,
        attempt=fixture.attempt,
        digest=digest,
        history_digest=history_digest,
        quarantine_versions=sorted(quarantine_versions),
        entries=history,
    )


def wait_for_visibility(check: Callable[[], tuple[Snapshot, str]]) -> tuple[Snapshot, str]:
    deadline = time.monotonic() + 90
    while True:
        try:
            return check()
        except (AssertionError, httpx.HTTPStatusError) as error:
            if isinstance(error, httpx.HTTPStatusError):
                if error.response.status_code not in {404, 429, 500, 502, 503, 504}:
                    raise
            if time.monotonic() >= deadline:
                raise
            print(f"Waiting for registry/package visibility: {redact_diagnostics(str(error), {})}", flush=True)
            time.sleep(3)


def validate_dashboard(html: str, fixture: Fixture, snapshot: Snapshot, history_only: bool) -> str:
    cards = [
        part.split("</article>", 1)[0]
        for part in html.split('<article class="image-card">')[1:]
        if f"<code>{fixture.quarantine}</code>" in part.split("</article>", 1)[0]
    ]
    assert len(cards) == 1, "The dashboard must contain exactly one fixture card"
    card = cards[0]
    assert f"Synchronized ({len(snapshot.entries)})" in card
    assert snapshot.digest[:19] in card
    for entry in snapshot.entries:
        assert entry.synced_at and entry.synced_at in card
        assert entry.run_url and entry.run_url in card
    assert (">not in quarantine<" in card) == history_only
    if history_only:
        assert "0 tag(s)" in card
    if any(entry.force for entry in snapshot.entries):
        assert ">forced</span>" in card
    return f'<article class="image-card">{card}</article>\n'


def check_live(
    phase: str,
    fixture: Fixture,
    digest: str,
    expected: Snapshot | None,
    copied: str | None,
    skipped: str | None,
    output: Path,
    execution_attempt: str | None,
) -> None:
    token = os.environ["GITHUB_TOKEN"]
    if not token:
        raise ValueError("GITHUB_TOKEN is required for live validation")
    environment = {
        "GITHUB_TOKEN": token,
        "GITHUB_OWNER": fixture.owner,
        "GITHUB_REPO": "cssc-framework",
        "GITHUB_OWNER_TYPE": os.environ.get("GITHUB_OWNER_TYPE", "user"),
        "GITHUB_USERNAME": os.environ.get("GITHUB_USERNAME", fixture.owner),
        "CACHE_TTL_SECONDS": "0",
    }
    with ExitStack() as stack:
        github = GitHubClient(token=token, cache_ttl=0)
        stack.callback(github.close)
        packages = stack.enter_context(serve("packages_service.app:app", environment))
        issues = stack.enter_context(serve("issues_service.app:app", environment))
        dashboard = stack.enter_context(serve("dashboard_web.app:app", {
            **environment,
            "PACKAGES_SERVICE_URL": packages,
            "ISSUES_SERVICE_URL": issues,
            "QUARANTINE_NAMESPACE": fixture.namespace,
        }))
        with httpx.Client(timeout=60) as client:
            def observe() -> tuple[Snapshot, str]:
                response = client.get(f"{packages}/packages", params={"namespace": fixture.namespace})
                response.raise_for_status()
                images = TypeAdapter(list[MirroredImage]).validate_json(response.content)
                assert [image.name for image in images] == [fixture.quarantine]
                response = client.get(f"{packages}/packages/{fixture.quarantine}/history")
                response.raise_for_status()
                history = TypeAdapter(list[MirrorHistoryEntry]).validate_json(response.content)
                if phase in {"initial", "forced"}:
                    assert execution_attempt and re.fullmatch(r"[1-9][0-9]*", execution_attempt)
                    assert history and history[-1].run_attempt == execution_attempt
                tags = []
                for repository in (fixture.quarantine, fixture.golden):
                    response = client.get(f"{packages}/packages/{repository}/tags")
                    response.raise_for_status()
                    tags.append(TypeAdapter(list[Tag]).validate_json(response.content))
                owner_root = {"user": "users", "org": "orgs"}[environment["GITHUB_OWNER_TYPE"]]
                versions = TypeAdapter(list[PackageVersion]).validate_python(github.get_all(
                    f"/{owner_root}/{fixture.owner}/packages/container/{quote(fixture.quarantine, safe='')}/versions",
                    params={"per_page": 100},
                ))
                snapshot = validate_state(
                    phase, fixture, tags[0], tags[1], history,
                    digest, expected, copied, skipped, {version.name for version in versions},
                )
                response = client.get(f"{dashboard}/stages/acquisition/fragment")
                response.raise_for_status()
                card = validate_dashboard(response.text, fixture, snapshot, phase in {"promoted", "skipped"})
                return snapshot, card

            snapshot, card = wait_for_visibility(observe)
            output.mkdir(parents=True, exist_ok=True)
            (output / "snapshot.json").write_text(snapshot.model_dump_json(indent=2) + "\n")
            (output / "acquisition.html").write_text(card)
    print(f"PASS: {phase}; {len(snapshot.entries)} history entries; registry, workflow and dashboard verified")


def cleanup(fixture: Fixture, client: httpx.Client) -> None:
    response = client.get(f"/users/{fixture.owner}")
    response.raise_for_status()
    owner_type = response.json()["type"]
    if owner_type == "Organization":
        root = f"/orgs/{fixture.owner}"
    elif owner_type == "User":
        response = client.get("/user")
        response.raise_for_status()
        if response.json()["login"].lower() != fixture.owner:
            raise ValueError("The deletion token must belong to the fixture owner")
        root = "/user"
    else:
        raise ValueError(f"Unsupported fixture owner type: {owner_type}")
    failures: list[str] = []
    for repository in (fixture.quarantine, fixture.golden):
        path = f"{root}/packages/container/{quote(repository, safe='')}"
        try:
            response = client.get(path)
            if response.status_code == 404:
                print(f"Fixture package already absent: {repository}")
                continue
            response.raise_for_status()
            response = client.delete(path)
            response.raise_for_status()
            deadline = time.monotonic() + 30
            while True:
                response = client.get(path)
                if response.status_code == 404:
                    break
                response.raise_for_status()
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Fixture package still exists after deletion: {repository}")
                time.sleep(1)
            print(f"Deleted and verified absent: {repository}")
        except (httpx.HTTPError, RuntimeError) as error:
            detail = f"{repository}: {redact_diagnostics(str(error), {})}"
            print(f"Fixture cleanup failed: {detail}", file=sys.stderr)
            failures.append(detail)
    if failures:
        raise RuntimeError("Fixture cleanup incomplete:\n" + "\n".join(failures))


def main() -> None:
    if not __debug__:
        raise RuntimeError("Run validation without -O or PYTHONOPTIMIZE; assertions are required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["coordinates", "initial", "promoted", "skipped", "forced", "cleanup"])
    parser.add_argument("--owner", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "").lower())
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT", ""))
    parser.add_argument("--execution-attempt")
    parser.add_argument("--digest", default="")
    parser.add_argument("--copied", choices=["true", "false"])
    parser.add_argument("--skipped", choices=["true", "false"])
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--output", type=Path, default=Path("mirror-history-evidence"))
    args = parser.parse_args()
    fixture = Fixture(args.owner, args.run_id, args.attempt)
    if args.phase == "coordinates":
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            for name, value in fixture.coordinates().items():
                output.write(f"{name}={value}\n")
        return
    if args.phase == "cleanup":
        token = os.environ["GITHUB_TOKEN"]
        if not token:
            raise ValueError("GITHUB_TOKEN is required for fixture cleanup")
        with httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        ) as client:
            cleanup(fixture, client)
        return
    expected = Snapshot.model_validate_json(args.expected.read_text()) if args.expected else None
    check_live(
        args.phase, fixture, args.digest, expected,
        args.copied, args.skipped, args.output, args.execution_attempt,
    )


if __name__ == "__main__":
    main()

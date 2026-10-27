# Validate mirror history end to end

Use the [mirror-history validation workflow](../../../.github/workflows/validate-mirror-history.yml)
to prove that a synchronized image is not acquired again after promotion removes
it from quarantine. This exercises the real mirror and promotion workflows,
GitHub Container Registry (GHCR), the package and issue services, and the
dashboard's rendered Acquisition view. Service checks use real local HTTP
servers on the runner, not mocked registry or service responses.

## Prerequisites and safety

- The repository must have a `GHCR_DELETE_TOKEN` secret with package read and
  deletion permissions. The same secret is already used by promotion.
- The workflow's built-in token needs `packages: write` for fixture publication.
- Live tests run only for same-repository pull requests or manual dispatch.
  Fork pull requests run the read-only tests without receiving secrets.
- Registry writes and deletes are restricted to two computed package paths:
  `ghcr.io/<owner>/quarantine/mirror-history-e2e-<run-id>-<attempt>/image` and
  `ghcr.io/<owner>/golden/mirror-history-e2e-<run-id>-<attempt>/image`.
  Normal quarantine and golden packages are never modified.

The fixture is a tiny scratch image containing a text file. It is first
published as `:upstream` in the disposable golden package, then treated as the
mirror's upstream. Using a controlled image avoids moving public tags and
changing vulnerability databases making the lifecycle test nondeterministic.
The normal Trivy scan and HIGH-severity promotion gate still run; neither
exceptions nor approval overrides are used.

## Run the validation

Changes to relevant actions, workflows, services, or the test harness trigger
the workflow on a pull request. After the workflow is on the default branch,
you can also run it from Actions, or with GitHub CLI:

```bash
gh workflow run validate-mirror-history.yml --ref main
gh run list --workflow validate-mirror-history.yml --limit 5
gh run watch <run-id> --exit-status
```

The run must pass all these checks:

| Phase | Required result |
| --- | --- |
| Initial mirror | The image digest is preserved, history has exactly one non-forced entry, and the workflow reports copied rather than skipped. |
| Promote and delete | The image reaches golden; the quarantine package's complete version inventory contains only the unchanged `mirror-history` artifact, with no tagged or untagged image/referrer versions left. |
| Mirror again | The workflow reports a history skip; the quarantine image remains absent and history is unchanged. |
| Force | The image is copied again and exactly one forced entry is appended without changing earlier entries. |
| Dashboard | The fixture card shows the digests, timestamps and run links; a history-only package has zero image tags and is marked not in quarantine. |
| Cleanup | Both disposable packages are deleted and verified absent. |

The workflow also runs regression tests, each service's tests, `actionlint`, and
`shellcheck -S warning` on its shell blocks.

The reusable [mirror workflow](../../../.github/workflows/_mirror-image.yml)
exposes `copied`, `skipped`, `digest`, and `run_attempt` outputs for these assertions. Its
optional `graph_events_artifact_name` defaults to the existing `graph-events`
name; callers invoking it repeatedly in one run must choose distinct names.

## Inspect evidence and failures

Each successful observation phase publishes a
`mirror-history-<phase>-<fixture-attempt>-<execution-attempt>`
artifact containing `snapshot.json` and the rendered fixture card
`acquisition.html`. Snapshots include the source digest and complete history,
the history artifact digest, and the quarantine version digests, but no
credentials. These artifacts are retained for 14 days. The initial observation
requires an actual referrer so deletion coverage cannot pass vacuously.

Visibility checks retry transient 404, 429 and server errors within a 90-second
deadline; authentication/authorization failures are immediate errors. Diagnostic
logs redact credentials and download-URL queries, including signed blob links.
The registry reader follows blob redirects without forwarding registry
authorization to another host; redirected-fetch errors retain the HTTP status
but omit signed query strings.

For success, the final `acceptance` job and `cleanup` must both pass. A green
mirror or promotion job alone is insufficient: deletion can otherwise be
skipped, and a history-only package could still be incorrectly shown in the
dashboard.

```bash
gh run download <run-id> --pattern 'mirror-history-*' --dir mirror-history-evidence
gh run view <run-id> --log-failed
```

The checks before publishing reject missing credentials. Subsequent failures
still invoke cleanup, including partial setup failures. Runs are not
automatically cancelled when a newer commit is pushed.

Partial job reruns reuse the fixture-creation attempt emitted by `prepare`,
rather than accidentally targeting the new execution attempt's package names.
The initial evidence artifact and each mirror's producing attempt are also
carried explicitly between jobs. Cleanup attempts both packages independently
and fails if either cannot be removed. For a fresh acceptance lifecycle,
dispatch a new run instead of replaying already-completed mutations.

If a runner is forcibly terminated before cleanup, obtain the original run ID
and attempt from that run, install the declared `cssc_common` dependencies, and
run the same guarded cleanup helper. Provide the deletion token through the
process environment as `GITHUB_TOKEN`; never place its value in shell history,
source files, or uploaded artifacts.

```bash
python tests/mirror_history/mirror_history_e2e.py cleanup \
  --owner <owner> --run-id <original-run-id> --attempt <original-attempt>
```

The helper only computes the two fixture package names; it does not accept an
arbitrary repository to delete. Authentication and deletion failures are
errors, not successful cleanup.

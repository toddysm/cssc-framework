# Mirror history artifact

Every repository the mirror workflows synchronize carries a **mirror-history**
OCI artifact recording the source digests already acquired for that repository.
It is written by the [`mirror-history`](workflow-actions.md#mirror-history)
action from the [`_mirror-image.yml`](../../.github/workflows/_mirror-image.yml)
workflow, and it lets the mirror skip a digest it has already synchronized once —
even after that digest has been promoted out of and deleted from quarantine.

The architecture and rationale are in
[docs/architecture/acquire/mirror-history.md](../architecture/acquire/mirror-history.md).

## Location

Stored under a **reserved tag** in the synchronized repository:

```
ghcr.io/<owner>/quarantine/<image>:mirror-history
```

`mirror-history` is never a valid upstream tag to mirror. Because it is a
separate tag it survives image-tag deletion during promotion (and keeps the
package alive, avoiding the GHCR "cannot delete the last tagged version" case).

## Format

- **manifest artifactType:** `application/vnd.toddysm.mirror-history.v1+json`
- **config mediaType:** `application/vnd.toddysm.mirror-history.v1+json`
  (a small summary blob: `schemaVersion`, `image`, `source`, `count`,
  `updated`), so the tag is self-describing and never mistaken for a
  runnable image.
- **layer mediaType:** `application/vnd.toddysm.mirror-history.v1+json`
- **manifest annotations:** `org.opencontainers.image.title=mirror-history.json`,
  `com.toddysm.mirror-history.count`, `com.toddysm.mirror-history.updated`.

The single layer blob is an append-only JSON log:

```json
{
  "schemaVersion": 1,
  "image": "ghcr.io/<owner>/quarantine/python",
  "source": "docker.io/library/python",
  "entries": [
    {
      "sourceTag": "3.14-slim",
      "sourceDigest": "sha256:...",
      "destTag": "3.14-slim",
      "syncedAt": "2026-07-30T06:00:00Z",
      "runUrl": "https://github.com/<owner>/cssc-framework/actions/runs/<id>",
      "runId": "<id>",
      "runAttempt": "1",
      "force": false
    }
  ]
}
```

- **History key** = `(sourceTag, sourceDigest)`. A digest is "already
  synchronized" when an entry matches both. `sourceDigest` is also the
  destination digest (the copy preserves digests).
- **Append-only, unbounded, chronological.** Entries are never removed; a `force`
  re-sync appends a new entry rather than mutating past ones.

## Behaviour

- On each mirror run the source digest is resolved and checked against the
  history. If the `(tag, digest)` is already recorded the copy is **skipped**
  (job summary: *skipped, already synchronized*), unless `force` is set.
- A recorded digest also suppresses the `copy_referrers` re-copy; `force`
  refreshes referrers on demand.
- After a run that actually copied (or found the destination already up to date)
  the digest is **recorded**. Skipped-by-history runs record nothing.

Controlled by the `record_history` input of `_mirror-image.yml` (default on).

## Retrieve

```bash
# Inspect the artifact manifest (annotations show count + last-updated):
crane manifest ghcr.io/<owner>/quarantine/python:mirror-history

# Pull the JSON log:
oras pull -o out ghcr.io/<owner>/quarantine/python:mirror-history
cat out/mirror-history.json | jq .
```

The CSSC Dashboard's Acquisition view surfaces this history per repository via
the `packages-service` `GET /packages/{name}/history` endpoint.

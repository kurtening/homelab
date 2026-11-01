# Daily operation and acceptance

## One read-only command

From a reviewed checkout with the repository-pinned tools available:

```bash
mise exec -- ./scripts/homelab-status
mise exec -- ./scripts/homelab-status --json
```

The command checks the active context before any cluster request, verifies the
single expected node, required Argo Applications, workload readiness and named
PVC bindings. It streams its own reviewed host-only mode over noninteractive
SSH, with strict existing host-key verification. Nothing is installed remotely.
Only expected mount flags, allowlisted unit metadata, collector timestamps and
hashes of twelve non-secret installed files are returned. It never invokes
sudo, reads credentials, accesses Restic, starts jobs, repairs drift or writes
host state. All subprocesses have timeouts; raw stdout/stderr is never forwarded.

Exit codes: **0** all operational checks passed; **2** unavailable access,
protected reads or incomplete evidence; **1** confirmed drift/failure or malformed
metadata. Offline desktop/cluster access is PENDING, not broken GitOps. Compare
against the intended reviewed checkout: unmerged edits can deliberately differ
from installed files. The checked-in contract is tested against tracked manifests.

Some executables and DynamicUser state cannot be read by SSH's unprivileged
user. Copy the reviewed script to the desktop and inspect explicitly:

```bash
scp scripts/homelab-status kurtening@krof-desktop:/tmp/homelab-status
ssh -t kurtening@krof-desktop 'sudo python3 /tmp/homelab-status --host --json'
```

This is read-only, not an installation. To aggregate a protected report, save
only its JSON locally outside the worktree with mode 0600, then pass its path
as `--host-report /protected/report.json`. Reports older than five minutes are
PENDING and cannot be reused as fresh evidence. Do not feed terminal/sudo
transcripts as JSON or publish raw reports. No credential or personal content
is needed for this check.

A service Result=success without an observable completion remains unknown.
The protected November 1 report matched all twelve installed file hashes and
showed fresh collector evidence and enabled timers. Minecraft's completion
timestamp was zero; the earlier operator-reported snapshot remains valid manual
evidence, but this missing timestamp cannot be promoted to a new service PASS.
Even an observed completion proves only a service invocation, not timer origin,
archive integrity, snapshot inclusion or restore readiness. Those require the
separate protected checks and private ledger below. A status PASS is deliberately
not full disaster-recovery acceptance.

## Redacted acceptance baseline — November 1, 2026

| Gate | Evidence | Remaining work |
| --- | --- | --- |
| Immich | Full isolated restore/rehearsal and production checks; post-upload snapshot `f04f1946` | First verified post-upgrade scheduled chain |
| Jellyfin | Strict content restore, independent credentials, one scheduled cycle | Seven distinct verified scheduled cycles before retiring stopped Compose |
| Minecraft | Operator-reported successful manual snapshot `71a80f59` at 21:39:47 Manila; verified isolated file retrieval/world gzip metadata; independent password copy verified; timer enabled | First scheduled cycle; server startup/gameplay recovery untested |
| Monitoring | Grafana/dashboard browser check and Discord firing/resolution operator-confirmed; required targets previously UP; Minecraft backup journal source/unit observed in Loki metadata | Explicit idle interval and operator confirmation of no gaming regressions |

During the operator-reported gaming interval approximately 21:39–22:09 Manila,
30 Prometheus samples showed a 564.3 MiB monitoring peak (including the existing
collector allowance), with zero monitoring-pod restarts. This is measured gaming
memory evidence, not an idle test or proof of user-perceived performance. Do not
declare full acceptance without the remaining operator/time-window checks.

The existing single November 2 **05:15 Asia/Manila** follow-up covers Immich and
Jellyfin only and must not be duplicated or rescheduled by this change.
Minecraft's first **05:30** cycle requires a separate check after completion;
do not count its November 1 manual snapshot as scheduled evidence. No automatic
retry or extra schedule is introduced.

For genuine scheduling, correlate timer trigger/service invocation and completion
with a fresh validated source/archive and subsequent snapshot inclusion. Jellyfin
also requires its CronJob-owned successful Job and scheduled timestamp, rejecting
manual-instantiation annotations; use the tracked `jellyfin-backup-status` helper.
Immich requires a fresh valid dump plus library, matching dump size/mtime in
the snapshot. Minecraft requires its timer-triggered successful invocation and
matching world snapshot. Missing protected access or an offline desktop is
PENDING; do not manufacture another backup to satisfy a scheduled check.

Keep the detailed ledger private: date/window, Job UID where applicable,
service invocation evidence, snapshot ID, integrity/inclusion result and review
time. Deduplicate cycles. Jellyfin remains at **one** verified cycle until new
evidence is recorded; successful probes and elapsed days do not increment it.
Retain stopped Compose, successful drill artifacts and previous installed backup
script. Cleanup requires separately approved exact targets; no broad pruning.

Off-machine backups and complete desktop-loss recovery remain unverified/deferred.

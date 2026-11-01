# Monitoring, logs and Discord alerts

## Activation declared; live acceptance requires evidence

PR #39 staged standalone manifests and encrypted credentials without connecting
the Applications. This separate activation change connects the `monitoring/`
child directory to the cluster root. Merging it can immediately reconcile both
Applications and start the stack: it is not another inert staging merge. Leave
the activation PR draft until the protected host preflight below passes and
the operator reviews the resource/storage/notification impact. No existing
application, backup timer, storage binding or Tailscale operator is changed.

The operator completed protected Discord entry and confirmed Grafana-password
vault custody. Silent credential validation passed. The new host collector was
installed on November 1, 2026; its unit reported success, DynamicUser, active/
enabled timer and MemoryMax=32 MiB. Direct kubelet TLS validated against the
projected Kubernetes CA during read-only preflight. The operator also reported
PASS from the protected exporter-UID bind-view/freshness/mount check and the
Alloy-UID/group journal-header check, without changing private-parent modes.
Actual service-account authorization, live ingestion, Discord delivery and
runtime-budget acceptance remain separate checks; no live stack acceptance is
implied by this document.

Prometheus, Alertmanager, Grafana, monolithic Loki, Alloy, Node Exporter,
kube-state-metrics and Blackbox Exporter are digest-pinned in the monitoring
Kustomization. Grafana alone receives Tailscale HTTPS ingress; there are no
public ports, host ports or external telemetry destinations except sanitized
Discord notifications. A dedicated ProxyClass limits only this new proxy.

The configuration targets less than 1 GiB working-set memory including a
32 MiB allowance for the host collector. It is not yet a measured guarantee.
Container limits total 1888 MiB; the ingress proxy adds 128 MiB and the host
collector 32 MiB, exactly 2 GiB. The monitoring namespace quota is 2016 MiB.
CPU limits, including the collector, total at most two cores. No GPU access is
used. Singleton Deployments use Recreate to avoid exceeding the quota during
updates; brief monitoring-only outages are acceptable. Node Exporter uses
OnDelete updates: an operator replaces only its monitoring pod after review.

New local-path claims request 11.5 GiB total: Prometheus/Loki 5 GiB each,
Grafana 1 GiB, Alertmanager/Alloy 256 MiB each. They are protected from pruning.
Requests are not filesystem quotas. History is disposable and excluded from
application backups; alert on underlying filesystem pressure. Prometheus keeps
three days or 3 GB of blocks (WAL/head add overhead); Loki compaction expires
logs after 24 hours plus its asynchronous deletion delay. Never delete claims
as part of rollback without separate approval.

## What is and is not monitored

During the staging read-only host preview on November 1, both expected mounts
matched and Immich/Jellyfin units exposed successful completion metadata.
`minecraft-restic-backup.service` returned LoadState=not-found. Its metrics
therefore report unavailable/unknown, and an activated stack should warn about
it after boot grace. This PR does not install or repair Minecraft backups;
review that separate prerequisite rather than hiding the alert.

- Host CPU/memory/filesystem space/inodes, expected data/backup filesystem UUIDs,
  Kubernetes readiness and PVCs/Jobs, Argo health, monitoring self-health,
  and kubelet container CPU/memory metrics. CPU gaming spikes do not page.
- Internal Immich/Jellyfin HTTP health and Minecraft TCP checks do not verify
  authentication, playback, outside DNS or tailnet reachability. Minecraft
  being idle/paused is not a failure if its socket remains available.
- Alloy reads pod logs through namespace-scoped roles only in `argocd`,
  `kube-system`, `tailscale`, and `monitoring`. It reads only the three backup
  services from persistent/volatile host journals with a one-hour startup
  lookback. It does not collect family-application pod logs, media, SQL dumps,
  Docker logs or arbitrary host journals. Journal GID 101 was observed on the
  desktop; recheck it before activation. No Docker or host D-Bus socket is
  mounted into Kubernetes. Logs stay private in Loki, never Discord or Git.
  A final pipeline drops lines matching webhook/auth/password/private-identity
  patterns or media/credential paths. This is defense in depth, not a guarantee
  that arbitrary vendor logs cannot contain sensitive data. Keep log access
  private and do not enable debug logging or broaden sources casually.
  Journal files contain multiple units: their read-only mount and journal
  group membership are broader than the configured three-unit filter. Trust
  the pinned collector image accordingly; this is not per-unit filesystem
  isolation.
- Node Exporter runs unprivileged with read-only host proc/sys/root mounts and
  a separate read-only mount of the collector's numeric textfile directory.
  It has no token, capabilities or writable host mounts. Read-only host-root
  visibility is still a trust boundary; root-protected files remain protected
  by the non-root UID and filesystem permissions.
- Prometheus uses TLS-verified direct kubelet metrics and `nodes/metrics`, not
  `nodes/proxy`. If its certificate/authorization check fails, stop activation
  and diagnose it; do not disable TLS verification or grant proxy permissions.
- The oneshot collector reads systemd properties and exact mount metadata.
  It never reads credentials, decrypts Restic, starts a backup, or interprets
  a service success as a restore/scheduled-chain PASS. It preserves observed
  successes across later failures and marks never-observed history unknown.

Grafana provisions five dashboards: host/storage, Kubernetes/Argo, backup
metadata, internal application probes and platform/backup logs. Provisioned
dashboards/datasources are Git-owned; do not rely on UI edits as configuration.

## Discord and protected credentials

Create a private Discord text channel such as `homelab-alerts`. In Server
Settings → Integrations → Webhooks, create a dedicated webhook bound to that
channel. Its URL is a capability credential: do not paste it into chat, a PR,
shell arguments/history, screenshots or plaintext files in this repository.

Use the existing age identity with `sops edit` on
`kubernetes/secrets/monitoring/monitoring-credentials.sops.yaml`. Set a private
mode-0700 TMPDIR outside the worktree for the editor session. Replace only
`DISCORD_WEBHOOK_URL`; retain the generated Grafana password and save a vault
copy under **Homelab — Grafana admin**, username `admin`. The encrypted
`GRAFANA_ROOT_URL` was derived privately from the existing tailnet suffix;
verify the issued ingress hostname matches it after activation. Remove the
`homelab.kurtening.dev/credential-status` annotation only after completing entry.

Validate locally without printing values:

```bash
SOPS_AGE_KEY_FILE=/protected/existing-age-identity mise exec -- python3 scripts/check-monitoring-credentials.py
```

A format/MAC PASS is not Discord delivery or independent vault custody proof.
Do not reuse an application database/Restic password. Grafana disables anonymous
access/signup and uses secure cookies. Its bootstrap admin password initializes
the database once: changing the Secret later does not rotate an existing
Grafana database password. Plan rotations separately. Alertmanager projects
only the webhook key; it cannot read the Grafana admin key. Grafana receives
only its own keys, not the webhook. Default notification templates are replaced
so no generator URL, private address, raw log, arbitrary annotation or mention
is included in Discord messages. Discord receives generic service/severity/
alert/state and a public runbook link only.

## Host prerequisite: explicit installation

This collector is new; merging does not install it. First inspect the reviewed
files, verify `krof-desktop`, mounts, available memory/disk, `systemd-journal`
group and journal directories, and confirm no existing files will be overwritten.
If an earlier collector exists, preserve it and review its differences first.

Copy the reviewed collector/unit/timer into a private staging directory on the
host, then run the read-only `homelab-metrics --check` preview. Only numeric
metadata and generic application/mount-role labels are printed. Existing backup
services/timers must remain unchanged throughout installation.

After review, use interactive sudo to install the collector at
`/usr/local/sbin/homelab-metrics` (root:root, 0755), and its service/timer at
`/etc/systemd/system/` (root:root, 0644). Run `systemd-analyze verify` on both
units, `systemctl daemon-reload`, then `systemctl enable --now homelab-metrics.timer`
and `systemctl start homelab-metrics.service`. Inspect its result and the
atomic textfile under `/var/lib/homelab-monitoring/textfile/` without reading
application data. Verify the DynamicUser, journal group, sandbox and memory
limit work on the actual host before allowing Kubernetes to depend on the path.

The reviewed `install-monitoring` helper in the same host directory performs
these exact steps, checks the hostname, and refuses to overwrite existing files.
After copying all four files together to private host staging, invoke it with
`sudo bash /protected/staging/install-monitoring`. Its failure is not activation
approval: inspect any partially installed collector files before retrying; do
not force overwrite. Stopping/disabling only this new timer is the rollback.

StateDirectory is 0755 so Node Exporter can read the bind-mounted textfile
directory; state.json stays 0600 and metrics 0644. No secrets are stored there.
DynamicUser places StateDirectory under a private parent; an unprivileged
host-shell traversal can correctly fail even though a root-created bind mount
exposes the numeric directory to the exporter. Do not chmod/chown
`/var/lib/private` or weaken systemd isolation to work around that observation.
Run `sudo python3 /protected/staging/check-monitoring-host` before merging
activation. It checks the installed hash, service/timer, directory/file modes,
fresh metrics and exact mount flags through a directory-FD view after dropping
to exporter UID 65534. It also tests a journal header as Alloy UID 473/group 101
without reading/displaying journal records. A PASS is a host preflight, not
proof of Kubernetes token authorization, live log ingestion or Discord delivery.
The state directory must exist before Node Exporter schedules; hostPath uses
Directory, never DirectoryOrCreate. A failed collection retains the previous
metrics, whose age triggers an alert instead of reporting a false fresh result.

## Activation and acceptance

The activation PR's only desired-state change connects the `monitoring` child
directory to the cluster root resources. Its topology test requires exactly
one of each reviewed child Application; staging's disconnection test was
deliberately transitioned in this separate change. Require credential/vault readiness and a healthy host
collector first. The secrets child has a creation sync wave, but that does not
prove its Secret is reconciled before workloads start. Verify the Secret keys
exist without exposing their values; wait for both Applications/PVCs/workloads
and the dedicated ingress proxy to become healthy.

1. Verify context `homelab-desktop` and reviewed main revision; check all required
   Prometheus targets, including verified kubelet TLS and Argo metrics.
2. Confirm Grafana HTTPS/login, provisioned dashboards, current numeric backup
   metadata, recent allowed platform/journal logs and absence of application
   namespace log targets. If no backup ran in the one-hour journal lookback,
   keep backup-log ingestion pending until the next natural execution; never
   restart or fabricate a backup just to populate the log dashboard. Do not
   dump log contents into reports.
3. Send a synthetic `HomelabMonitoringTest` alert through Alertmanager, then
   resolve it. Label it clearly as a test; verify Discord firing and resolved
   messages contain only approved fields. Never stop applications or damage
   backups to manufacture test failures. Do not leave the test alert active.
4. Observe at least 30 idle minutes and one normal operator gaming session.
   Require less than 1 GiB aggregate working set including collector allowance,
   no monitoring OOMs, no application regressions, healthy retention/ingestion
   and bounded disk use. If the budget fails, stop and revise; do not silently
   increase limits. Keep live acceptance PENDING until evidence exists.

Backup failures alert after five minutes. Unknown history waits until the host
has been up for one hour, then five minutes. Backups older than 26 hours wait
15 minutes and are suppressed while a backup runs and during boot grace.
Two-hour running backups warn after five minutes. Wrong mounts alert after five
minutes; space/inodes warn below 15% for 30 minutes and become critical below
5% for five minutes. Workload/probe failures wait ten minutes; Argo Degraded
waits ten and OutOfSync fifteen. Collector/scrape/ingestion/notification failures
and OOM/budget rules are tracked in the alert config. No arbitrary log-string
or high-CPU pages are configured. Notifications group for 30 seconds, update
at most every five minutes and repeat after 12 hours; resolved alerts notify.

Planned power-offs produce no notifications while the on-host stack is off.
There is no independent observer: complete host/monitoring failure and broken
Discord delivery cannot reliably notify through this same stack. Check the
private dashboard/delivery metrics if notifications are suspect. No external
uptime service or off-machine data shipment is introduced.

## Validation and rollback

Run the repository Kubernetes validator publicly and with the protected identity.
Run the collector tests (standard library), manifest tests and pinned config
validators after installing `scripts/requirements-monitoring.txt` into a test
venv. Use `mise exec --` so Kustomize is pinned. `scripts/validate-monitoring.py`
uses local Docker with a disposable credential-helper configuration, immutable
images, no networking in validators, read-only source mounts, temporary test
storage and a synthetic webhook file; it never receives production credentials.
Public CI performs these same checks. Run existing backup regression tests too.

Rollback the activation through a reviewed GitOps change; application deletion
must be deliberate because merely removing a parent reference may not cascade
without an Application resource finalizer. Verify and explicitly delete only
the monitoring Applications/workloads if required by that reviewed rollback.
Keep PVCs/Secrets and all existing application resources intact. Disable only
`homelab-metrics.timer` with interactive sudo; retain collector files/state and
all telemetry data pending separate cleanup approval. No broad pruning.

The Jellyfin scheduled-cycle hold, one-time verification follow-up, restored
test artifacts, and off-machine-backup deferral are unaffected.

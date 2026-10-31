# Jellyfin operations

Jellyfin is running as one Kubernetes replica with an enabled daily backup
CronJob. LAN access, private Tailscale HTTPS, and production users, libraries,
watch history, playback, and applicable transcoding checks were confirmed by
the operator after cutover. Compose remains stopped for rollback.

The two instances share SQLite state and must never run simultaneously. The
historical cutover checklist below also applies to any future reactivation.

Retained storage, the SOPS-managed API key, Service, and Tailscale Ingress are
managed by Argo CD. Host backup assets are installed and the 04:30 Manila timer
is enabled; merging Git changes does not update installed host files. Manual
archive creation and Restic snapshots/checks passed. Scheduled-chain evidence
is a separate acceptance check, described below.

## Deployment contract

The manifests depend on these existing host paths:

| Purpose | Host path | Container path |
| --- | --- | --- |
| Configuration | `/mnt/data-drive-2tb/jellyfin/config` | `/config` |
| Cache and transcodes | `/mnt/data-drive-2tb/jellyfin/cache` | `/cache` |
| Media root | `/mnt/data-drive-2tb/Media` | `/media` (read-only) |

The media mount preserves the configured library paths `/media/Anime`,
`/media/Movies`, and `/media/Series`. The state and media volumes are retained,
host-specific local volumes bound to `krof-desktop`; their declared capacities
control Kubernetes binding and do not impose filesystem quotas.

The migrated state contains files owned by both root and UID 1000. The server
runs as root with all capabilities dropped except `DAC_OVERRIDE`, allowing it
to access that existing state without recursive ownership changes. Keep
`allowPrivilegeEscalation: false`, RuntimeDefault seccomp, and the read-only
media mount. Moving to a non-root runtime requires a separately reviewed
ownership migration; changing only `runAsUser` will break access to existing
files.

Jellyfin uses the immutable official 10.11.11 image digest recorded in the
Deployment. Stable upgrades are explicit GitOps changes and require a backup,
release-note review, and a new verified image digest. Do not replace it with the
mutable `latest` tag.

## Backup credential

The encrypted `jellyfin-backup-api-key` Secret contains a dedicated credential.
During initial staging it used an unusable placeholder. If bootstrapping again
or deliberately replacing the credential:

1. In the running Jellyfin instance, create a dedicated API key named
   `homelab-jellyfin-backup` under **Dashboard > API Keys**.
2. Set `SOPS_AGE_KEY_FILE` to the protected homelab age identity.
3. Edit
   `kubernetes/secrets/jellyfin/jellyfin-backup-api-key.sops.yaml` with the
   pinned `sops` tool, replace `stringData.API_KEY`, and remove the
   `homelab.kurtening.dev/credential-status` annotation.
4. Confirm `sops filestatus` reports encrypted status and run the full protected
   Kubernetes validation without printing the decrypted value.

The CronJob runs at 04:00 Asia/Manila and calls Jellyfin's built-in online
backup endpoint. It includes the database, metadata, subtitles, and trickplay.
The CronJob is enabled by the activation change and remains suspended if that
change is reverted.
Backup creation is a non-idempotent POST, so neither curl nor the Job retries
it automatically. After failure, inspect the server and archive directory
before manually retrying to avoid overlapping backup creation.

## Host Restic installation

The built-in archive is copied to a dedicated local Restic repository by a
host systemd timer at 04:30 in the host's local timezone. Verify that timezone
before enabling it; the Kubernetes CronJob explicitly uses Asia/Manila.
Media and disposable cache contents are excluded.
The timer waits up to 30 minutes for an archive created within the previous two
hours, then retains 7 daily, 4 weekly, and 6 monthly snapshots and runs
`restic check`. A candidate archive must be nonempty and pass `unzip -tqq`
before it counts as fresh; a ZIP still being written does not satisfy this gate.

These are manual host operations, not automatic GitOps steps. Verify both mount
UUIDs against the script, the host timezone, `restic` and `unzip` availability,
and the source configuration directories before installation. Initialize the
dedicated repository and password file only if they do not already exist;
never overwrite an existing password or reinitialize an existing repository.
Then install the tracked host files:

```bash
sudo bash <<'ROOT'
set -euo pipefail
umask 077
repository=/mnt/backup/homelab/jellyfin/repository
password=/etc/restic/jellyfin-password
[[ "$(findmnt -rn -M /mnt/backup -o UUID)" == 3180031e-abd5-4d6a-8aac-abe3e41dc950 ]]
[[ "$(findmnt -rn -M /mnt/backup -o FSTYPE)" == ext4 ]]
[[ ! -L "$repository" && ! -L "$password" ]]
if [[ -f "$repository/config" && ! -s "$password" ]]; then
  echo 'Existing repository requires its existing password' >&2; exit 1
fi
if [[ -d "$repository" && ! -f "$repository/config" &&
      -n "$(find "$repository" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo 'Nonempty directory without Restic config; inspect manually' >&2; exit 1
fi
if [[ ! -e "$password" ]]; then
  install -d -m 0700 /etc/restic
  (set -o noclobber; openssl rand -base64 48 >"$password")
fi
[[ -s "$password" && "$(stat -c '%u:%a' "$password")" == 0:600 ]]
export RESTIC_REPOSITORY="$repository" RESTIC_PASSWORD_FILE="$password"
if [[ ! -f "$repository/config" ]]; then
  install -d -m 0700 "$repository"
  restic init
fi
restic snapshots >/dev/null
ROOT

sudo install -m 0755 \
  host/krof-desktop/backup/jellyfin/jellyfin-restic-backup \
  /usr/local/sbin/jellyfin-restic-backup
sudo install -m 0644 \
  host/krof-desktop/backup/jellyfin/jellyfin-restic-backup.service \
  /etc/systemd/system/jellyfin-restic-backup.service
sudo install -m 0644 \
  host/krof-desktop/backup/jellyfin/jellyfin-restic-backup.timer \
  /etc/systemd/system/jellyfin-restic-backup.timer
sudo systemctl daemon-reload
```

The credential block never truncates an existing password or reinitializes an
existing repository. Preserve an independent recovery copy if a new password
is generated. SSH commands from this project normally use
`kurtening@krof-desktop`; privileged checks/installations require interactive
sudo. Never send a sudo password, Restic password, or age identity through chat.

Leave the timer disabled until the real API key is configured, Kubernetes
Jellyfin is running, and a manually triggered CronJob has produced a valid
archive. After the host service succeeds and its snapshot is verified, enable
the timer with `sudo systemctl enable --now jellyfin-restic-backup.timer`.

The repository is on a separate local device, but it remains inside the same
desktop and is not off-site protection. `restic check` is not a restore test.

## Cutover reference (completed)

1. Merge the staged resources while `Deployment.spec.replicas` is `0` and
   `CronJob.spec.suspend` is `true`.
2. Verify the three Applications are Synced and have no manifest-generation
   errors. Inspect PV/PVC names, storage class, capacities, node affinity, host
   mounts, and directory permissions. The StorageClass uses
   `WaitForFirstConsumer`: PVCs may remain Pending and Application health may
   remain Progressing until the first server pod is scheduled. Do not start a
   consumer or change binding policy merely to make staging appear Healthy.
3. Create a built-in backup from the running Compose instance and verify the
   archive exists under `/mnt/data-drive-2tb/jellyfin/config/data/backups`.
4. Stop, but do not remove, the Compose container:

   ```bash
   cd /home/kurtening/jellyfin
   docker compose stop jellyfin
   ```

5. Confirm no process is listening on host port 8096.
6. In a separate activation change, set the Deployment to one replica and set
   the CronJob `suspend` field to `false`; merge through the normal GitOps path.
   First replace the encrypted API-key placeholder and verify the current
   Compose version matches the pinned Kubernetes image. Any version mismatch
   requires a separate upgrade review and compatible backup before cutover.
7. Confirm both PVCs are Bound to their intended PVs, all three Applications
   are Healthy, then verify the `/health` endpoint, LAN access on host port 8096, Tailscale HTTPS,
   users, watch state, all libraries, direct playback, and transcoding.
8. Trigger the CronJob once, verify its successful completion and ZIP integrity,
   run the host Restic service, and verify a snapshot before enabling the timer.

Never run Compose and Kubernetes Jellyfin simultaneously against the shared
configuration database.

## Rollback

Revert the activation change so Argo CD returns the Deployment to zero replicas
and suspends the CronJob. Wait until the pod has terminated and port 8096 is
free, then restart the unchanged Compose service:

```bash
cd /home/kurtening/jellyfin
docker compose start jellyfin
```

Keep the Compose definition and container through an initial soak period. A
future version upgrade may migrate the database; reverting the image after such
an upgrade requires restoring a compatible backup rather than merely changing
the image tag.

## Repeatable restore verification

The tracked `host/krof-desktop/backup/jellyfin/jellyfin-restore-drill` uses Python
3's standard library, Restic, Docker, and an already-present image matching the
tracked server manifest. Copy the helper and that manifest to the host, then
run it with interactive sudo:

```bash
scp host/krof-desktop/backup/jellyfin/jellyfin-restore-drill \
  kubernetes/apps/jellyfin/server.yaml kurtening@krof-desktop:/tmp/
ssh -t kurtening@krof-desktop \
  'sudo python3 /tmp/jellyfin-restore-drill SNAPSHOT_ID --manifest /tmp/server.yaml'
```

Replace `SNAPSHOT_ID` with an explicit Jellyfin snapshot ID, not `latest`.
For resumption add `--resume /mnt/backup/jellyfin-restore-drill.RUN_ID`; only
private, root-owned directories created by this helper with matching snapshot
and image metadata are accepted. Each attempt gets fresh test state and unique
container names. Legacy ad-hoc drill directories have no resume marker and are
not accepted; retain them for inspection instead of changing their metadata.

The drill verifies the expected mount UUIDs and restores files with
`restic restore --verify`. It finds the newest Jellyfin ZIP inside the restore
tree, checks its integrity and version, and refuses missing/corrupt archives
rather than silently falling back to older data.

Initialize a fresh isolated database **before** importing the archive: this
Jellyfin version restores before initial schema migrations. The helper uses
two stopped-between-stages containers with network disabled, no published
ports, two CPUs, an 8 GiB memory/swap ceiling, and read-only media. It requires
at least 12 GiB available host memory; defer the drill during gaming or other
heavy desktop use. Production configuration is never mounted.

HTTP health alone is insufficient: the setup endpoint may answer before the
import completes. Require the explicit restore-completion and startup log
markers, then cleanly stop the test server and compare the archive's users,
catalog IDs/paths/types, played/resume fields, and library configuration against
the restored database/files. The archive is the point-in-time baseline, not
the evolving production database. Missing fields or mismatches fail the drill.

Console output contains counts and PASS/FAIL only. Logs, aggregate reports, and
sample differences remain in private host artifact directories. The helper
stops its containers on success/failure but never deletes diagnostic state.
Run synthetic coverage locally with:

```bash
python3 scripts/test-jellyfin-recovery.py
```

### Verified scope and remaining recovery gaps

On November 1, 2026, the stricter isolated drill verified Restic file recovery,
ZIP integrity, archive import completion, healthy startup, user identities,
catalog mappings, library definitions, and watch/resume records. The earlier
2 GiB health-only attempt ran out of memory during import and was a false
positive; it is not recovery evidence. Production remained unaffected.

The Restic password recovery copy is operator-confirmed. On November 1, 2026,
the operator verified the independent vault copy of the SOPS age identity:
its derived public recipient matched `.sops.yaml` and it decrypted repository
ciphertext silently. No identity rotation was performed. This application
drill does not prove host-loss recovery, media recovery, or off-machine backup
availability. Media and disposable cache are deliberately excluded from this
Restic repository.

## Scheduled backup acceptance and rollback retention

The first scheduled chain must be checked after 04:30 Manila time, allowing
until 05:15 for completion. Copy the read-only helper to the host and run:

```bash
scp host/krof-desktop/backup/jellyfin/jellyfin-backup-status kurtening@krof-desktop:/tmp/
ssh -t kurtening@krof-desktop 'sudo python3 /tmp/jellyfin-backup-status'
```

It requires a successful CronJob-owned Job with the scheduled-time annotation
and rejects `cronjob.kubernetes.io/instantiate: manual` (manual cutover Jobs
also have CronJob owner references). It correlates the archive's creation time,
ZIP integrity, and size/mtime in a later Restic snapshot, then checks the
enabled timer's trigger and successful service result. Exit 0 is verified,
2 is pending, and 1 is a failed/unverifiable check. The snapshot listing proves
inclusion; the separately tested restore establishes recoverability.

At this update only the manual chain is verified; do not label it scheduled
evidence. If the desktop is off, record the check as pending and verify the
next completed cycle. Keep a private record of seven successful scheduled
cycles before considering retirement of stopped Compose.

Inventory the exact stopped test containers and plaintext restore directories
before cleanup. Retain them until content verification/evidence is recorded,
then request approval for those exact targets. Do not automatically delete
Compose, production paths, Restic repositories, credentials, or drill artifacts.

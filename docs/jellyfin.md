# Jellyfin operations

Jellyfin declares one Kubernetes replica and an enabled daily backup CronJob.
Stop Compose before merging the activation change: the two instances share
SQLite state and must never run simultaneously. Follow the cutover procedure
below, including backup verification and the rollback sequence.

Retained storage, the SOPS-managed API key, Service, and Tailscale Ingress are
managed by Argo CD. Host scripts and systemd units require manual installation;
enable the Restic timer only after Kubernetes backup verification succeeds.

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

1. In the running Compose instance, create a dedicated API key named
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

These are manual cutover operations, not staging-PR steps. Verify both mount
UUIDs against the script, the host timezone, `restic` and `unzip` availability,
and the source configuration directories before installation. Initialize the
dedicated repository and password file only if they do not already exist;
never overwrite an existing password or reinitialize an existing repository.
Then install the tracked host files:

```bash
sudo install -d -m 0700 /mnt/backup/homelab/jellyfin/repository
sudo install -d -m 0700 /etc/restic
sudo install -m 0600 /dev/null /etc/restic/jellyfin-password
sudoedit /etc/restic/jellyfin-password

sudo env \
  RESTIC_REPOSITORY=/mnt/backup/homelab/jellyfin/repository \
  RESTIC_PASSWORD_FILE=/etc/restic/jellyfin-password \
  restic init

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

Leave the timer disabled until the real API key is configured, Kubernetes
Jellyfin is running, and a manually triggered CronJob has produced a valid
archive. After the host service succeeds and its snapshot is verified, enable
the timer with `sudo systemctl enable --now jellyfin-restic-backup.timer`.

The repository is on a separate local device, but it remains inside the same
desktop and is not off-site protection. `restic check` is not a restore test.

## Cutover

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

## Restore verification

Before describing the backup as recoverable, restore a built-in archive into an
isolated Jellyfin instance pinned to the same version. Use a copied temporary
state directory, do not mount production state read-write, and verify users,
libraries, and watch history. Deleting or replacing production state requires a
separate reviewed recovery procedure.

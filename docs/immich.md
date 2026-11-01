# Immich recovery and upgrade operations

Immich currently runs server and machine learning v3.1.0 on the single-node
K3s cluster. Production upgrade to v3.3.5 is gated on a full isolated restore
and migration rehearsal, followed by a reviewed GitOps change. No production
image or storage change is included in the recovery tooling PR.

## Backup boundary

The installed host job creates a plain PostgreSQL dump using `pg_dump --clean
--if-exists`, gzip-validates it, and snapshots `library` and `database-dumps`
under `/mnt/data-drive-2tb/homelab/immich` into the dedicated Restic repository
`/mnt/backup/homelab/immich/repository`. Its password is
`/etc/restic/immich-password`, separate from Jellyfin and the SOPS age identity.
Verify an independent password recovery copy without displaying it in chat.

The timer runs at 03:00 host local time (currently Asia/Manila). A successful
backup or `restic check` is not application recovery proof. The database dump
and library copy are not atomic while writers remain active; production
upgrade requires a final checkpoint during coordinated write quiescence.

Uploaded files and the database are required together. The model-cache PVC is
reproducible cache and is not backed up. External-library assets require their
own explicit mounts/backups; none were found in the current deployment.

## Read-only preflight and image inventory

Confirm the kube context before diagnostics:

```bash
kubectl config current-context  # expected homelab-desktop
kubectl get deployment,statefulset,pvc -n immich
kubectl exec -n immich immich-postgres-0 -c postgres -- \
  psql -U postgres -d immich -X -Atc \
  'SELECT extname, extversion FROM pg_extension ORDER BY extname'
```

Record exact running image digests and the application version in a protected
image-inventory JSON outside the worktree. Required keys are `version`,
`server`, `machine_learning`, `postgres`, `valkey`, and an `extensions` mapping
from the query above. Each image must use its reviewed repository and
`@sha256:` digest; do not resolve recovery against a mutable tag.

The database image currently matches the v3.3.5 upstream deployment:
PostgreSQL 14 with VectorChord 0.4.3 and pgvector 0.8.1. Keep PostgreSQL and
Valkey images unchanged during this application upgrade. Record their exact
digests rather than copying transient values from conversation history.

Verify both mountpoints, expected device UUIDs, source paths, available space,
installed backup units, and Restic snapshots. On the host, use interactive sudo
for repository inspection; never export the password or kubeconfig:

```bash
ssh -t kurtening@krof-desktop \
  'sudo env RESTIC_REPOSITORY=/mnt/backup/homelab/immich/repository RESTIC_PASSWORD_FILE=/etc/restic/immich-password restic snapshots --host krof-desktop --tag immich'
```

## Full isolated restore

Copy the tracked helper and the reviewed image inventory to a private staging
directory on the host. Run it with an explicit snapshot ID:

```bash
sudo python3 /protected/staging/immich-restore-drill SNAPSHOT_ID \
  --images /protected/staging/baseline-images.json
```

The helper uses only Python 3's standard library, Docker, Restic, `findmnt`, and
GNU `cp`. It validates mount UUIDs and requires at least twelve GiB available
host memory. Free backup storage must cover three full snapshot sizes plus
ten GiB. Defer heavy restores during gaming or other interactive desktop use.
The application library is approximately 49 GiB at preparation time.

The sequence is:

1. Verify that the selected snapshot belongs to this host's Immich repository;
   pull the exact reviewed image digests.
2. Restore the entire snapshot and verify file content with Restic. Locate one
   database dump and its adjacent library without assuming absolute paths in
   the restore tree. Validate the gzip stream and COPY sections completely.
3. Initialize a disposable PostgreSQL instance with the unchanged production
   database image. Restore the SQL in one transaction with `ON_ERROR_STOP=on`.
   Apply upstream's `public, pg_catalog` restore search-path adjustment.
4. Before application startup, compare hashed COPY rows for every backed-up
   public table and check extension versions. This is content validation, not
   merely PostgreSQL readiness.
5. Verify every active original's recorded checksum against files in the
   restored library. Fail for missing originals, unsupported checksum types,
   external paths, or path/symlink escapes.
6. Copy verified media into fresh writable test state. Start server/database/
   cache services on a uniquely named internal-only Docker network with no
   published ports and disposable credentials. Include only the API worker;
   background workers and outbound connectivity are disabled.
7. Require API ping and initialized-application checks, then stop the test
   server and compare user identities, asset ownership/paths/checksums,
   album metadata/membership, and library identity fields against the dump.
8. Check machine-learning startup separately, without downloading models or
   claiming inference coverage. Stop all owned services afterward; retain
   private data, logs, and the unused internal network for diagnosis.

The active test stack stays below eight GiB/four CPUs. PostgreSQL is capped at
two GiB/one CPU, server at four GiB/two CPUs, and cache at 256 MiB/0.25 CPU.
Machine learning is tested only after the server stops, capped at two GiB/
0.75 CPU. No GPU access, privileged containers, production mounts, credentials,
Kubernetes resources, or live data are changed by the drill.

Console output is aggregate progress and PASS/FAIL only. SQL dumps and service
logs can contain private data; keep them in the root-owned mode-0700 artifact
directory outside Git. Resumption accepts only a directory created by this
helper with matching snapshot/source-image metadata:

```bash
sudo python3 /protected/staging/immich-restore-drill SNAPSHOT_ID \
  --images /protected/staging/baseline-images.json \
  --resume /mnt/backup/immich-restore-drill.RUN_ID
```

Each attempt initializes fresh database/runtime copies. Do not remove retained
data or stopped services without reviewing the exact cleanup targets.

## Upgrade rehearsal and production gates

After baseline recovery passes, prepare a second inventory with both server
and machine-learning images pinned to verified v3.3.5 digests. Preserve the
PostgreSQL, Valkey, and extension inventory exactly. Rehearse on another fresh
copy from the same verified snapshot:

```bash
sudo python3 /protected/staging/immich-restore-drill SNAPSHOT_ID \
  --images /protected/staging/baseline-images.json \
  --target-images /protected/staging/target-images.json \
  --resume /mnt/backup/immich-restore-drill.RUN_ID
```

The baseline phase runs again before the upgrade phase. Successful migrations,
initialized startup, preserved core metadata, originals, and ML startup are
required. Do not reset facial recognition, enable new sharing features, opt
into revised models, or run bulk regeneration jobs during this upgrade.

The target comparison explicitly expects the upstream
[AlbumDescriptionNullable migration](https://github.com/immich-app/immich/blob/v3.3.5/server/src/schema/migrations/1784986754474-AlbumDescriptionNullable.ts):
empty album descriptions become SQL `NULL`. Only the expected v3.3.5 baseline
is transformed; actual rows are not normalized. Nonempty descriptions and all
other selected fields must still match exactly. The initial rehearsal stopped
on this representation change; isolated database comparison confirmed it was
the only difference across the five checked metadata tables. The corrected
full rehearsal subsequently passed for both versions, including separate
machine-learning startup checks. This does not exercise ML inference or model
downloads, authenticated browsing, original downloads, or video playback.

Publish the paired application-image change as a separate draft PR only after
the live isolated rehearsal passes. Review intervening release notes and mobile
client compatibility. The target v3.3.5 release includes security fixes.

### Reviewed application-image change

The upgrade PR changes server and machine learning together to the exact
digest-pinned v3.3.5 images exercised by the successful isolated rehearsal.
PostgreSQL, Valkey, GPU configuration, credentials, resource settings, and
storage bindings remain unchanged. Review the two manifest image references
against the retained target inventory before the maintenance window.

Merge the recovery-tooling PR first and review the image change separately
against `main`. Do not merge the image PR just because its schema checks pass:
once automation is restored, Argo can start migrations immediately. The
independent Restic recovery password, agreed write pause, verified final
checkpoint, captured previous image digests and Argo policies, and compatible
client versions are prerequisites. Do not reopen uploads until production
acceptance and the controlled-upload backup check pass.

The rehearsal proves fresh restoration of the selected checkpoint into the
old version and migration of another fresh copy into the target version.
It does not prove an in-place database downgrade, a production rollback, or
restoration of a final maintenance-window snapshot not yet created. Rollback
must recreate the old database/library state from that final checkpoint;
never reuse the migrated database with the old images.

Before production merge, coordinate a write pause with every uploading client,
quiesce the server using an approved maintenance/GitOps sequence, run the
installed backup service, and verify its new snapshot. Argo self-healing must
not silently undo quiescence: a plain imperative scale-down is insufficient.
The operator-selected exception is a temporary Argo auto-sync pause and
scale-down, not a persistent manifest change. During the agreed window:

1. Verify context and save the original `syncPolicy` of both `cluster-root`
   and `immich` Applications into a protected local artifact. Confirm neither
   has an active sync operation. Pause root automation first, then child
   automation; the self-healing parent otherwise can undo a child-only pause.
2. Confirm uploads and other writers are paused. Scale the Immich server and
   machine-learning Deployments to zero and wait for their pods to terminate.
   Keep database/cache running. Verify Argo is not recreating the writers.
3. Run the installed backup service with interactive sudo. Require success
   and verify the new database/media snapshot; record its ID, previous image
   digests, and rollback prerequisites before requesting the upgrade merge.
4. After operator review/merge, refresh the child and verify its desired
   revision and paired target digests before syncing. Restore the captured
   child automation policy, sync the reviewed revision, and check migrations
   and health before restoring the captured parent policy. Do not overwrite
   unrelated policy fields or enable automation that was originally disabled.
5. On any failure, leave clients paused and report the maintenance state.
   Restoring auto-sync before deciding which database/image pair is safe can
   restart incompatible writers; follow the rollback checkpoint procedure.

No pause, scale-down, backup installation, or production restore is performed
by the recovery helper or by merging its tooling PR.

After operator review/merge, verify migrations and workload readiness, HTTPS,
login, timeline, albums, original downloads, playback, and ML inference with
existing models. Perform one controlled upload and a successful subsequent
backup before reopening normal uploads. Leave PostgreSQL/Valkey and all retained
bindings/reclaim policies unchanged.

## Rollback and evidence

Immich does not support downgrading an upgraded database. A tag revert alone
is not rollback. Stop writers, preserve failed state, and restore the final
pre-upgrade database/library checkpoint before starting the prior application
digests. Review exact host targets and the recovery procedure before any
production restore; never delete/recreate retained PVs/PVCs or format mounts.

Record these gates separately:

| Gate | Current evidence |
| --- | --- |
| Scheduled backup and repository check | November 1 host job reported success |
| Full file/database/media recovery | Operator-run baseline passed: all 66 dump tables, 5,455 active original checksums, five core metadata tables, v3.1.0 startup and ML startup |
| v3.3.5 isolated migration rehearsal | Operator-run corrected rehearsal passed: migrations, all 66 restored dump tables, 5,455 active original checksums, five core metadata tables, initialized startup, and separate ML startup; no inference/playback claim |
| Production upgrade acceptance | Not started; still v3.1.0 |
| Post-upgrade backup | Not applicable yet |
| Independent Immich Restic password recovery | Operator confirmed November 1: independent vault copy unlocked the Immich repository using the hidden-prompt verifier; PostgreSQL password remains separate |

Run synthetic coverage with `python3 scripts/test-immich-recovery.py`. CI does
not receive production credentials or media. Off-machine protection and full
host-loss recovery remain separate work.

Primary references: [v3.3.5 release](https://github.com/immich-app/immich/releases/tag/v3.3.5),
[versioned upgrade guidance](https://github.com/immich-app/immich/blob/v3.3.5/docs/docs/install/upgrading.md),
[v3.1.0 recovery procedure](https://github.com/immich-app/immich/blob/v3.1.0/docs/docs/administration/backup-and-restore.md).

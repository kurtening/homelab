# Rebuild and host-loss recovery

This is an ordered recovery blueprint, **not a tested cold-restore procedure**.
Do not execute it on the working desktop to test it. It does not authorize a
reinstall, datastore copy, production restore, credential rotation or storage
replacement. A real end-to-end drill remains PENDING until a suitable isolated
environment exists. No off-machine application-data backup currently exists;
total desktop loss can therefore still mean permanent data loss.

## Verified baseline — November 1, 2026

| Dependency | Observed state / recorded contract |
| --- | --- |
| Host | `krof-desktop`, Pop!_OS 24.04 LTS, single K3s node; also used for gaming |
| K3s | `v1.36.2+k3s1`, active host systemd service, SQLite datastore |
| K3s data | Standard `/var/lib/rancher/k3s`; server token file exists, independent custody **unverified** |
| K3s configuration | One YAML source under the standard config/drop-in layout; protected network settings present, deliberately not published |
| Data mount | `/mnt/data-drive-2tb`, ext4 UUID `cb3505ce-970c-49c2-ad50-4bc07ddbe508` |
| Backup mount | `/mnt/backup`, independent ext4 UUID `3180031e-abd5-4d6a-8aac-abe3e41dc950` |
| Host backup tool | Restic `0.16.4`; three separate repository/password pairs |
| Host automation | Three `*-restic-backup` scripts/services/timers plus `homelab-metrics`; manually installed, not delivered by merge |
| Cluster bootstrap | Argo installation, first root Application and `argocd/sops-age` require manual bootstrap |
| External access | Host Tailscale, tailnet authorization/DNS, and Sunshine remain outside GitOps |

These are dated observations, not reasons to downgrade a newer reviewed host.
The protected inventory helper emits only an allowlisted summary:

```bash
scp scripts/homelab-rebuild-inventory kurtening@krof-desktop:/tmp/homelab-rebuild-inventory
ssh -t kurtening@krof-desktop 'sudo python3 /tmp/homelab-rebuild-inventory'
```

It requires host Python/PyYAML, root access and the expected hostname; all commands
are bounded reads. K3s process environment/configuration is inspected in memory
to account for overrides, but never emitted verbatim. Private addresses, tokens,
datastore endpoints and arbitrary settings are excluded. The server token file's
presence is checked without opening its contents. Custom config/data locations
stop with PENDING rather than being guessed. The summary cannot replace the
protected original configuration needed for an exact rebuild.

## Recovery material and custody

Before any recovery operation, obtain independently held material and record
availability privately. GitHub `main`, a local clone, and an in-cluster Secret
are not independent copies of everything needed here.

| Material | Custody/evidence |
| --- | --- |
| Existing SOPS age identity | Independent vault copy previously verified against recipient and ciphertext |
| Immich, Jellyfin and Minecraft Restic passwords | Separate independent vault copies verified; preserve existing values |
| Grafana administrator password | Operator-confirmed vault copy; telemetry itself is disposable |
| Original K3s server token | File exists; independent copy and verification PENDING |
| Private K3s network configuration and host mount/service configuration | Independent protected recovery copy PENDING; do not publish raw files |
| Tailscale authorization/OAuth recovery and provider/backend access | Availability and recovery access must be checked privately; not proven by manifests |
| Minecraft bootstrap seed | Untracked Secret; confirm private recovery source, including protected backed-up server configuration; never regenerate a world to recover it |
| Application data | Local encrypted repositories and successful scoped drills; no off-machine copy |

For restoring the **existing datastore**, preserve its original server token
with the datastore backup. K3s uses that token to decrypt datastore bootstrap
data; a different token makes the backup unusable. The current datastore is
SQLite, so an etcd-snapshot recipe is not applicable. The SQLite recovery source
is the server database directory plus the matching token. No verified K3s
datastore backup is currently evidenced. [Official K3s backup/restore](https://docs.k3s.io/datastore/backup-restore)

Do not copy a live SQLite directory and label it consistent without validating
the backup method and its WAL handling. Creating a datastore backup, arranging
token custody or stopping K3s needs a separate reviewed operational step. Never
print the token, put it in arguments/chat, or silently create a replacement.

## Ordered rebuild gates

Default blueprint: **fresh cluster from reviewed Git plus verified application
restores**. Restoring a verified existing K3s datastore is a separate recovery
track, not a prerequisite or an automatic fallback. It can resurrect old
Applications and credentials; do not start that control plane against unprepared
production storage. Obtain a reviewed maintenance/recovery plan first.

1. **Select and preserve recovery sources.** Identify explicit snapshot IDs,
   compatible application/database images and independent credentials. Preserve
   failed state when available. Never initialize an existing Restic repository,
   replace its password or overwrite a source directory. Check space for full
   restores and retained evidence. No destructive cleanup is implied.
2. **Prepare the host.** Restore/review OS prerequisites, hostname, time zone,
   host networking/Tailscale and exact K3s network settings before starting K3s.
   Mount the expected independent devices and validate UUID, filesystem, writable
   state and ownership. Never format a device to make a missing mount check pass.
   Do not recursively chown restored data as a shortcut. Inventory required K3s,
   Restic, Python/PyYAML, Bash, util-linux, gzip/unzip and Docker tooling before
   using the corresponding operation. Host recovery must preserve the gaming/GPU
   setup; no reinstall or GPU change is part of this documentation PR.
3. **Bootstrap K3s deliberately.** Use the observed/reviewed version and recovered
   private settings, not an unpinned installer default. Do not assume a fresh
   stock configuration reproduces the private networking. Verify node identity,
   kube context, DNS, local-path and internal-only Traefik behavior. For an
   initially stock install, hold client access and explicitly apply the reviewed
   `kubernetes/platform/traefik` bootstrap override before exposing application
   routes; the later root Application does not protect the pre-GitOps interval.
   For an
   existing-datastore restore, follow its reviewed offline procedure with the
   original token instead; never overlay a database into a running K3s process.
   [K3s configuration precedence](https://docs.k3s.io/installation/configuration)
4. **Bootstrap Argo/KSOPS without the root Application.** Create the `argocd`
   namespace, recover `sops-age` from the protected identity, then install the
   tracked pinned Argo/KSOPS bootstrap. This order avoids repo-server's missing
   age-volume failure. Follow `secret-management.md`; keep decrypted output out
   of files/logs. Verify repository rendering. Do **not** apply `cluster-root`
   or its self-managing child before the remaining gates are ready.
5. **Prepare retained storage and application credentials.** Verify the exact
   static paths, node affinity, storage classes, reclaim protections and existing
   directory ownership against manifests and the private inventory. Bootstrap
   storage explicitly if needed without creating consumer Applications; retained
   PVCs may stay Pending under `WaitForFirstConsumer` until an approved first
   consumer schedules. Render/recover application Secrets through protected
   KSOPS workflows, preserving their existing values; verify identities/key sets
   without displaying values. Recover the Minecraft seed privately.
6. **Restore application data before opening writers.** Follow each application's
   reviewed runbook from explicit snapshots into isolated/staging paths first.
   Production replacement requires separate approval. Immich needs full library
   and compatible PostgreSQL dump/extensions; do not reuse the drill's disposable
   credentials in production. Jellyfin needs schema initialization then archive
   import; media is excluded from its backup, and Compose must remain stopped.
   Minecraft's current verified scope is file retrieval/world metadata only;
   startup/gameplay still needs an isolated test. Never run two instances against
   shared state. Match restored data to image versions and rehearse any migration
   before handing control to current `main`.
7. **Release GitOps and ingress only after review.** Once data, credentials and
   host dependencies are ready, review the exact root revision and its automatic
   sync/prune effects, then bootstrap `cluster-root`. If any consumer is not
   ready, keep the root absent; do not rely on a plain scale-down surviving
   self-healing. Verify storage Bound status, migrations, Argo/workload health,
   private HTTPS/TCP access and authenticated application behavior. Tailnet
   access is external state, not something Git alone recreates.
8. **Restore backup operation last.** Install reviewed host scripts/units only
   through explicit interactive sudo, preserving recovered passwords/repositories.
   Keep timers disabled until each manual backup and required recovery checks
   pass. Persistent timers can run immediately after activation/boot. Verify a
   later genuine scheduled cycle independently; no manual run substitutes for
   it. Reinstall monitoring's separate collector only after its own preflight.

## Isolated drill and rollback requirements

A future full rebuild drill needs a reviewed, isolated machine/VM with sufficient
RAM/disk, restored copies and private diagnostic storage. Never attach it to
production PVCs, reuse a live host's Tailscale identity, restore production
auto-sync into the live cluster, or publish ports accidentally. No test VM is
created by this change. Use synthetic fixtures for tooling in CI, never real
credentials or databases.

Acceptance must separately prove host bootstrap, storage/credential recovery,
Argo/KSOPS rendering, application content/startup, private access, and subsequent
backup operation. Record timing and actual recovered-data age before claiming
an RTO/RPO; neither is measured yet. Keep operator playback/gameplay checks
distinct from pod health and repository checks.

If a future drill fails, stop only its test services and retain protected logs
and restored copies. If production recovery fails, hold writers and GitOps,
preserve failed state, and use the application's reviewed checkpoint rollback.
An image revert does not reverse Immich database migrations. Never delete or
recreate retained PVs/PVCs, credentials, Restic data or stopped Compose as an
automatic recovery action. This blueprint does not change today's recovery
limitations or authorize cleanup.

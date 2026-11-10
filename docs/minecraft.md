# Minecraft

Minecraft runs as a private, single-instance Java Edition server on the
`krof-desktop` K3s node. Argo CD owns the Kubernetes workload, while the world
uses retained local storage. Restic job assets are tracked here, but their
installation and verification are separate host operations.

The Deployment runs one replica. Its retained storage directory, bootstrap seed,
Restic repository, and tailnet access are required runtime dependencies.

## Server contract

- Minecraft Java Edition `26.1.2`
- Fabric loader `0.19.3`
- Fabulously Optimized client pack `13.3.0`
- survival mode, normal difficulty, PvP disabled
- online authentication with tailnet membership as the only admission boundary
- Tailscale-only TCP access on port `25565`
- one-player sleep and fast leaf decay
- native pause after the server has been empty for ten minutes
- the Excalibur `26.1_01` resource pack is required for all players

The client pack is not installed on the server. The server downloads these
exact Modrinth releases at startup:

| Project | Version | Modrinth version ID |
| --- | --- | --- |
| Fabric API | `0.154.2+26.1.2` | `lOQ4tyDD` |
| Lithium | `0.24.6` | `fQBdPR1m` |
| FerriteCore | `9.0.0` | `d5ddUdiB` |
| Leaves Us In Peace | `1.12.0` | `OZtHERvr` |

Minecraft, Fabric, the container image, and every mod are intentionally pinned.
Treat upgrades as reviewed migrations: take a fresh backup, change one version
set, validate startup and gameplay, and retain the prior pins for rollback.

## Manual prerequisites

First verify that the active kube context targets the intended cluster. Then
verify the data and backup mounts by mountpoint, filesystem, and device UUID;
the backup script repeats these checks every time it runs.

Create the world directory on the data filesystem before the storage
Application reconciles:

```bash
sudo install -d -o 1000 -g 1000 -m 0750 \
  /mnt/data-drive-2tb/homelab/minecraft
```

Do not regenerate credentials or initialize a repository merely because the
backup service is missing. The November 1, 2026 read-only host check found an
existing repository and a working dedicated password, but **zero matching
snapshots** and no installed backup executable/service/timer. That is not backup
coverage. The operator subsequently installed the reviewed job, completed manual
snapshot `71a80f59` at 21:39:47 Manila, passed isolated file/world-gzip verification
and independent password comparison, and enabled the timer for November 2 at
05:30 Manila. Scheduled execution and server startup/gameplay recovery remain
unverified. Preserve the existing password and repository.

For a genuinely new host, provision a dedicated password and repository only
after verifying both are absent and the expected independent backup device is
mounted. A missing password beside existing ciphertext is a recovery problem,
not permission to create a replacement password. Stop and recover the existing
credential rather than initializing or overwriting anything.

The Restic password requires independent recovery. The local repository does
not protect against theft, fire, or loss of the entire desktop.

## Bootstrap seed

After the staging change has merged and Argo CD has created the `minecraft`
namespace, create the untracked bootstrap Secret. The seed must exist before
the first server start because it is consumed during world generation.

```bash
kubectl config current-context
kubectl get nodes

seed_dir="$(mktemp -d)"
chmod 0700 "${seed_dir}"
read -r -s -p 'Minecraft seed: ' minecraft_seed
printf '\n'
printf '%s' "${minecraft_seed}" >"${seed_dir}/seed"
unset minecraft_seed

kubectl --namespace minecraft create secret generic minecraft-bootstrap \
  --from-file="seed=${seed_dir}/seed"

rm -f -- "${seed_dir}/seed"
rmdir -- "${seed_dir}"
```

Do not print, decode, or commit the Secret. The generated `server.properties`
file on retained storage will also contain the seed and is protected by host
access controls and the encrypted Restic repository.

## Runtime and access

Confirm that `minecraft-data` remains bound to the intended PV and that the
bootstrap Secret exists without inspecting its value:

```bash
kubectl --namespace minecraft get persistentvolumeclaim minecraft-data
kubectl get persistentvolume minecraft-data
kubectl --namespace minecraft get secret minecraft-bootstrap \
  --output name
```

The server replica count is managed through GitOps. Do not scale it directly
with `kubectl`; Argo CD self-healing would revert that mutation.

The Tailscale operator exposes the Service as `minecraft` on TCP port `25565`.
Tailnet policy is external to this repository and allows tailnet members to
reach the operator-managed service. Minecraft's whitelist is disabled, so any
tailnet member with an authenticated Minecraft account can join. Do not enable
Funnel, router port forwarding, or a public DNS record.

Players install Fabulously Optimized `13.3.0` for Minecraft `26.1.2`, join the
tailnet, and connect to:

```text
minecraft.<tailnet>.ts.net:25565
```

Use the private tailnet suffix from the Tailscale admin console; never commit it.

On connection, clients download the pinned Excalibur ZIP directly from Modrinth
and must accept it to join. The configured SHA-1 is for that exact release;
verify the new ZIP and hash together before updating either. If the download is
unavailable or rejected, players cannot join until it is available or the pack
settings are reverted through GitOps. Basic textures work with unmodified Java
clients; some visual features require compatible client-side mods. Test both
the documented Fabulously Optimized client and a vanilla client before merging.
Use an isolated server and world for these tests. Change the Deployment's
resource-pack revision annotation when updating the pack so Argo CD rolls the
pod and the container reads the updated ConfigMap.
The server rollout restarts Minecraft; verify a current backup and arrange a
quiet window before merging. To roll back, revert the three resource-pack
settings and wait for Argo CD to reconcile the resulting restart.

## Operators

Operator assignments are live application state and must not be committed to
this public repository. After the pod is ready, manage them through the
in-container RCON client:

```bash
minecraft_pod="$(
  kubectl --namespace minecraft get pods \
    --selector app.kubernetes.io/name=minecraft \
    --output jsonpath='{.items[0].metadata.name}'
)"

kubectl --namespace minecraft exec "${minecraft_pod}" \
  --container minecraft -- rcon-cli op OPERATOR_NAME
```

The RCON port is exposed only through the cluster-internal admin Service.

## Private administration console

The proposed console uses its own Tailscale HTTPS endpoint and individual
accounts. Its RCON Service is internal, and NetworkPolicies restrict access to
the Minecraft pod and console proxy. Tailscale policy is external: explicitly
grant the console device only to the owner and selected co-admins. Sharing the
game device does not itself share this console. Verify policies on live K3s;
the presence of a NetworkPolicy manifest does not prove enforcement.

**Do not merge before provisioning and testing.** The committed encrypted
admin Secret contains only `PENDING` placeholders. From a private terminal on
the administration laptop, generate and save a separate console password in
the password vault. Set `SOPS_AGE_KEY_FILE` to the existing protected identity,
verify the active kube context and Minecraft health, then run:

```bash
mise exec -- python3 scripts/minecraft/create-admin-secret.py
mise exec -- python3 scripts/minecraft/create-admin-secret.py --verify
```

The pinned console initializes its RCON callback queue incorrectly, causing the
first command to execute without returning its result. An init container checks
the expected source and patches that queue for Minecraft RCON only. The patched
console returned a first `list` response against both a mock and a disposable
Minecraft server. Two sequential commands returned matching responses against
the mock; restart and error behavior remain to be tested before activation.
A command timeout never proves it did not execute.
The image also uses Node 12 and salted MD5 password hashes; its security
suitability remains unresolved.

The helper refuses to replace non-placeholder credentials, captures the current
RCON password privately, prompts twice without echoing for the console password,
and derives the console WebSocket URL,
encrypts them, and checks the password against the running server. It does not
display values. Review and commit only the encrypted file. Run `--verify`
again immediately before merge; a server restart changes its current generated
password. If verification fails, do not merge. Run the helper with
`--refresh-rcon`, then `--verify`; this retains the console password and captures
the current RCON value. Review and commit the new ciphertext before merging.
Never print credentials, pass them in shell arguments or paste them into chat.

The console has a retained local-path PVC for accounts; it is not covered by
the Minecraft world backup. Independently protect the admin credential and plan
to recreate co-admin accounts if this database is lost. Restrict access through
the host filesystem: the console database may contain RCON credentials and
account information, and must not be copied into this public repository. Use
an encrypted backup if the database is added to a future backup workflow.
Restrict access through
the Tailscale admin console, then add and remove individual accounts inside the
web console. Confirm each co-admin and an unshared player with separate devices.
The console image uses Node 12 and its upstream authentication uses salted MD5
for passwords, which is unsuitable for modern password storage. Treat it as a
privileged legacy service and keep it private. Verify its HTTPS, WebSocket, permissions and RCON behavior
on an isolated server before activation. No public port forwarding or Funnel.

Before merge verify a current backup, no running backup and a quiet window. The
server restart switches from an automatically generated RCON password to the
captured stable value; verify `rcon-cli` and backup save coordination afterwards.
Revert the admin change to remove the console and resume generated credentials;
preserve the retained console PVC and encrypted Secret until separately reviewed.

## Backup installation and verification

A merge records the backup files but does not install them. Use a reviewed copy
of `host/krof-desktop/backup/minecraft/` on `krof-desktop`; development is normally
on a separate laptop. Root checks and installation need a private local terminal
with interactive sudo (`ssh -t` remotely). Never send sudo/Restic passwords to
chat or pass passwords as command arguments.

Run the read-only preflight first from that directory:

```bash
sudo python3 ./check-minecraft-backup
```

It checks exact writable mount identities, nonempty world metadata, a protected
existing password and read-only repository access; only aggregate results are
printed. It does not read/display player data or initialize anything. If it
fails, resolve the prerequisite without replacing existing credentials.

After review, install with:

```bash
sudo bash ./install-minecraft-backup
```

The installer refuses the wrong host, existing destination files/symlinks or an
existing service. It installs only Minecraft backup files and validates their
units. **It does not enable the timer or start a backup.** If validation fails
after copying, leave the timer disabled and inspect the installed files before
retrying; do not overwrite them blindly.

The daily 05:30 **Asia/Manila** job validates both mounts, asks Minecraft to flush
and suspend world saves, snapshots the full data directory, immediately resumes
saves, applies 7-daily/4-weekly/6-monthly retention, and runs `restic check`.
It refuses overlapping invocations. RCON is bounded to 60 seconds per request;
the copy is bounded to two hours. Recovery is armed before `save-off`, so an
ambiguous transport failure still attempts `save-on`. INT/TERM also exit through
that trap. This is best-effort recovery, not a guarantee through SIGKILL, host
loss, or an unreachable server. If recovery fails, use the in-container RCON
client to issue `save-on` and investigate before retrying. Never leave saving
disabled to make a failed backup appear successful. RCON coordinates world
flushes; a live full-directory copy is not an atomic snapshot of every changing
log/configuration file or a tested full application recovery.

Run the first backup explicitly and inspect its result:

```bash
sudo systemctl start minecraft-restic-backup.service
sudo systemctl show minecraft-restic-backup.service \
  --property=Result --property=ExecMainStatus --property=ExecMainExitTimestamp
sudo env RESTIC_REPOSITORY=/mnt/backup/homelab/minecraft/repository \
  RESTIC_PASSWORD_FILE=/etc/restic/minecraft-password \
  restic snapshots --host krof-desktop --tag minecraft --latest 1
```

Inspect any journal failure locally; do not paste raw logs/player data. Confirm
the selected snapshot includes the intended full data root. Restore that
**explicit snapshot ID** using the reviewed helper from that same host directory:

```bash
sudo python3 ./verify-minecraft-recovery SNAPSHOT_ID
```

It checks the snapshot's host/tag/source contract and available space, restores
with verification into a new mode-0700 directory on the verified backup device,
locates nonempty `world/level.dat` without assuming an absolute restore layout,
and gzip-tests it without printing contents. Retain protected drill output until
cleanup is explicitly approved.
This checks verified file retrieval and world metadata, **not** isolated server
startup, gameplay, or complete host-loss recovery. Never mount restored data
into production or start a second server against the live world.

Save the existing `/etc/restic/minecraft-password` independently as
**Homelab — Minecraft Restic recovery password** in the vault, distinct from
Immich, Jellyfin and the SOPS identity. Verify the saved copy at a hidden prompt
against this repository, without printing/writing the candidate or passing it
in command arguments:

```bash
sudo python3 ./check-minecraft-backup --verify-vault-password
```

Custody is pending until that comparison succeeds. Do not substitute the
Minecraft seed/RCON password or another application's Restic password.

Only after successful manual backup, isolated file verification and recovery
custody, enable scheduling explicitly:

```bash
sudo systemctl enable --now minecraft-restic-backup.timer
sudo systemctl list-timers minecraft-restic-backup.timer --no-pager
```

The timer is persistent: a missed run may execute after the desktop boots.
Its first genuine scheduled success must be verified separately from the manual
test. Monitoring's next minute-based collection will discover the unit and its
observed result automatically; no monitoring restart or alert suppression is
needed. An installed unit alone must not be reported as successful backup.

For rollback of this new host installation, disable only
`minecraft-restic-backup.timer`. If the service is active, let it finish when
possible; if stopped, confirm `save-on` succeeds. Leave the installed files,
repository, password and restore evidence in place for review. No world/PVC,
server Deployment, existing backup service, or monitoring change is required.

## Rollback and recovery

For an application failure, return the Deployment to zero replicas through Git
or revert the workload revision. The retained PV and PVC must remain in place.

Before replacing world data, stop the Deployment through GitOps, take an
additional snapshot when possible, restore into a separate directory, inspect
the result, and obtain explicit approval for the final replacement. Never run
two server instances against the same world.

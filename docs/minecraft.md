# Minecraft

Minecraft is staged as a private, single-instance Java Edition server on the
`krof-desktop` K3s node. Argo CD owns the Kubernetes workload, while the world
uses retained local storage and a host-installed Restic job.

The initial manifest deliberately sets the Deployment to zero replicas. Do not
activate it until the storage directory, bootstrap seed, Restic repository, and
tailnet access have been prepared and verified.

## Server contract

- Minecraft Java Edition `26.1.2`
- Fabric loader `0.19.3`
- Fabulously Optimized client pack `13.3.0`
- survival mode, normal difficulty, PvP disabled
- online authentication and an enforced Minecraft whitelist
- Tailscale-only TCP access on port `25565`
- one-player sleep and fast leaf decay
- native pause after the server has been empty for ten minutes

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

Create a dedicated Restic password and repository without placing the password
in the worktree or shell history:

```bash
backup_secret_dir="$(mktemp -d)"
chmod 0700 "${backup_secret_dir}"
openssl rand -base64 48 >"${backup_secret_dir}/minecraft-password"

sudo install -d -m 0700 /etc/restic
sudo install -m 0600 \
  "${backup_secret_dir}/minecraft-password" \
  /etc/restic/minecraft-password
sudo install -d -m 0700 /mnt/backup/homelab/minecraft/repository

sudo env \
  RESTIC_REPOSITORY=/mnt/backup/homelab/minecraft/repository \
  RESTIC_PASSWORD_FILE=/etc/restic/minecraft-password \
  restic init

rm -f -- "${backup_secret_dir}/minecraft-password"
rmdir -- "${backup_secret_dir}"
```

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

## Activation and access

Before activation, confirm that `minecraft-data` is bound to the intended PV
and that the bootstrap Secret exists without inspecting its value:

```bash
kubectl --namespace minecraft get persistentvolumeclaim minecraft-data
kubectl get persistentvolume minecraft-data
kubectl --namespace minecraft get secret minecraft-bootstrap \
  --output name
```

Activate the server through a focused GitOps change that sets the Minecraft
Deployment replica count from zero to one. Do not scale it directly with
`kubectl`; Argo CD self-healing would revert that mutation.

The Tailscale operator exposes the Service as `minecraft` on TCP port `25565`.
Tailnet policy is external to this repository and must allow tailnet members to
reach the operator-managed service. Do not enable Funnel, router port forwarding,
or a public DNS record.

Players install Fabulously Optimized `13.3.0` for Minecraft `26.1.2`, join the
tailnet, and connect to:

```text
minecraft.<tailnet>.ts.net:25565
```

Use the private tailnet suffix from the Tailscale admin console; never commit it.

## Whitelist and operators

Player names and operator assignments are live application state and must not be
committed to this public repository. After the pod is ready, manage them through
the in-container RCON client:

```bash
minecraft_pod="$(
  kubectl --namespace minecraft get pods \
    --selector app.kubernetes.io/name=minecraft \
    --output jsonpath='{.items[0].metadata.name}'
)"

kubectl --namespace minecraft exec "${minecraft_pod}" \
  --container minecraft -- rcon-cli whitelist add PLAYER_NAME
kubectl --namespace minecraft exec "${minecraft_pod}" \
  --container minecraft -- rcon-cli op OPERATOR_NAME
```

The RCON port is cluster-internal and is not exposed by a Service.

## Backup installation and verification

A merge records the backup files but does not install them. After the server is
active, install the script and units manually on `krof-desktop`:

```bash
sudo install -m 0755 \
  host/krof-desktop/backup/minecraft/minecraft-restic-backup \
  /usr/local/sbin/minecraft-restic-backup
sudo install -m 0644 \
  host/krof-desktop/backup/minecraft/minecraft-restic-backup.service \
  /etc/systemd/system/minecraft-restic-backup.service
sudo install -m 0644 \
  host/krof-desktop/backup/minecraft/minecraft-restic-backup.timer \
  /etc/systemd/system/minecraft-restic-backup.timer

sudo systemctl daemon-reload
sudo systemctl enable --now minecraft-restic-backup.timer
```

The daily 05:30 Asia/Manila job validates both mounts, asks Minecraft to flush
and suspend world saves, snapshots the full data directory, immediately resumes
saves, applies 7-daily/4-weekly/6-monthly retention, and runs `restic check`.
Its exit trap attempts to resume saves after any failure.

Run the first backup explicitly and inspect its result:

```bash
sudo systemctl start minecraft-restic-backup.service
sudo systemctl status minecraft-restic-backup.service
sudo journalctl --unit minecraft-restic-backup.service --since today
```

For a non-destructive restore check, restore the latest snapshot into a protected
temporary directory on a filesystem with enough free space and verify that it
contains a non-empty `level.dat`. Do not restore over the live data directory.
This checks Restic retrieval and basic world presence, not a complete cold-start
recovery drill.

## Rollback and recovery

For an application failure, return the Deployment to zero replicas through Git
or revert the workload revision. The retained PV and PVC must remain in place.

Before replacing world data, stop the Deployment through GitOps, take an
additional snapshot when possible, restore into a separate directory, inspect
the result, and obtain explicit approval for the final replacement. Never run
two server instances against the same world.

# homelab

> [!WARNING]
> **Work in progress.** This repository describes a functioning personal
> homelab, but it is not yet a complete disaster-recovery system. Host
> provisioning, complete credential recovery, off-machine backups, and a full
> host-loss recovery procedure are still missing. Jellyfin has a verified
> isolated application restore; that does not cover the entire homelab.

A GitOps-managed, single-node K3s homelab running on `krof-desktop`, a desktop
used for both gaming and homelab workloads. Argo CD reconciles Kubernetes
configuration from GitHub `main`, Tailscale provides private application
ingress, and OpenTofu/Terragrunt records the repository's GitHub governance.

## Current system

| Area | Implementation | Delivery and recovery status |
| --- | --- | --- |
| Kubernetes | Single-node K3s | Host installation and initial bootstrap are manual |
| GitOps | Argo CD app-of-apps | Kubernetes resources reconcile automatically from `main` |
| Applications | Immich, Minecraft, Jellyfin, and `whoami` | Minecraft and Jellyfin run as singletons; Compose Jellyfin remains stopped for rollback |
| Private ingress | Tailscale Kubernetes Operator | OAuth Secret is SOPS-encrypted in Git; tailnet policy remains external |
| Persistent storage | Static local Immich, Minecraft, and Jellyfin PVs | Retained and bound to `krof-desktop` |
| Backups | Application-consistent archives and Restic snapshots | Jellyfin restore/content and first scheduled-chain checks passed; local only |
| Repository policy | OpenTofu/Terragrunt | Planned and applied manually with remote state |

Only Argo-managed Kubernetes resources change automatically after a merge.
K3s, host files, mounts, backup installation, infrastructure applies, the SOPS
age bootstrap, Restic credentials, and tailnet configuration remain manual
operations.

## Repository layout

```text
.
├── host/                         # Host-level scripts and systemd units
├── infrastructure/               # OpenTofu/Terragrunt GitHub governance
├── kubernetes/
│   ├── apps/                     # Application manifests
│   ├── bootstrap/argocd/         # Pinned Argo CD installation
│   ├── clusters/krof-desktop/    # App-of-apps and retained local storage
│   ├── platform/                 # K3s platform overrides
│   └── secrets/                  # SOPS-encrypted Kubernetes Secrets
├── docs/architecture.md          # Detailed current architecture
└── scripts/                      # Repository validation helpers
```

## Deployment prerequisites

The declared configuration assumes an operator has already provided:

- `krof-desktop` with K3s, the local-path provisioner, and packaged Traefik
- the expected data and backup filesystems, directories, ownership, and mounts
- the SOPS age identity and bootstrap Secret, plus application-specific Restic passwords
- initialized Restic repositories on the backup mount
- the untracked Minecraft seed Secret before the Minecraft Deployment is activated
- access to GitHub, the Tailscale Helm repository, and validation schema hosts
- Azure and GitHub authentication for repository-governance changes

These dependencies are not automated here. This list is a deployment contract,
not a tested bootstrap or recovery runbook. Verify storage and credentials
before allowing the root Argo CD Application to reconcile dependent workloads.

## Known recovery gaps

- Host and K3s provisioning are not automated.
- The SOPS age identity and host credentials require independent recovery.
- The Restic repository is local to the same desktop and has no off-machine
  copy.
- No cold-restore drill has proven recovery of PostgreSQL, media, credentials,
  and application availability.
- Jellyfin's isolated application restore/content checks, independent
  age-identity recovery verification, and first scheduled backup chain passed.
  See the Jellyfin runbook for the current evidence scope and retention gates.

Retained PV/PVC policies and `Prune=false,Delete=false` protections reduce
accidental deletion risk, but they are not backups.

## Validation

Pinned local tools are declared in `mise.toml`. The complete component-specific
commands and safety rules are in [AGENTS.md](AGENTS.md); the scripts and GitHub
Actions workflows are authoritative when prose elsewhere is incomplete.

For Kubernetes manifest changes, the primary local check is:

```bash
mise exec -- ./scripts/validate-kubernetes.sh
```

This check renders manifests and downloads schemas; it requires network access
but does not contact a live cluster. OpenTofu/Terragrunt changes must also run
the formatting and validation commands mirrored from the IaC workflow.

## Project documentation

- [Architecture](docs/architecture.md) explains ownership, reconciliation,
  networking, storage, backups, and trust boundaries.
- [Jellyfin operations](docs/jellyfin.md) covers the Compose migration,
  backup setup, cutover, and rollback.
- [Immich operations](docs/immich.md) covers full database/media recovery,
  isolated upgrade rehearsal, maintenance gates, and rollback requirements.
- [Secret management](docs/secret-management.md) covers SOPS/age custody,
  Argo CD bootstrap, validation, and recovery.
- [Minecraft](docs/minecraft.md) covers the private server, tailnet access,
  seed bootstrap, operator administration, backups, and recovery.
- [Agent instructions](AGENTS.md) define repository-wide change and validation
  safeguards.
- [Contributing](CONTRIBUTING.md) describes the contribution workflow.
- [Security policy](SECURITY.md) explains what must not be published and how to
  report sensitive findings.

This repository is licensed under the terms in [LICENSE](LICENSE).

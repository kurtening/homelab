# homelab

> [!WARNING]
> **Work in progress.** This repository describes a functioning personal
> homelab, but it is not yet a complete disaster-recovery system. Host
> provisioning, credential recovery, off-machine backups, and a tested restore
> procedure are still missing.

A GitOps-managed, single-node K3s homelab running on `krof-desktop`, a desktop
used for both gaming and homelab workloads. Argo CD reconciles Kubernetes
configuration from GitHub `main`, Tailscale provides private application
ingress, and OpenTofu/Terragrunt records the repository's GitHub governance.

## Current system

| Area | Implementation | Delivery and recovery status |
| --- | --- | --- |
| Kubernetes | Single-node K3s | Host installation and initial bootstrap are manual |
| GitOps | Argo CD app-of-apps | Kubernetes resources reconcile automatically from `main` |
| Applications | Immich and `whoami` | Declared under `kubernetes/apps/` |
| Private ingress | Tailscale Kubernetes Operator | OAuth Secret is SOPS-encrypted in Git; tailnet policy remains external |
| Persistent storage | Static local Immich PVs | Retained and bound to `krof-desktop` |
| Backups | PostgreSQL dump and Restic snapshot | Local only; no tested cold restore or off-machine copy |
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
- the SOPS age identity and bootstrap Secret, plus the Restic repository password
- an initialized Restic repository on the backup mount
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
- [Secret management](docs/secret-management.md) covers SOPS/age custody,
  Argo CD bootstrap, validation, and recovery.
- [Agent instructions](AGENTS.md) define repository-wide change and validation
  safeguards.
- [Contributing](CONTRIBUTING.md) describes the contribution workflow.
- [Security policy](SECURITY.md) explains what must not be published and how to
  report sensitive findings.

This repository is licensed under the terms in [LICENSE](LICENSE).

# Homelab agent instructions

## Scope

These instructions apply to the entire repository.

Before making changes, read the relevant repository files, plus:

- `SECURITY.md` for public-repository safety rules.
- `CONTRIBUTING.md` for the contribution workflow.
- `docs/architecture.md` for the current system design.

Treat repository state as authoritative. Conversation history and agent memory are useful context, but they must not override the manifests, scripts, or documentation on the current branch.

## Operating model

- `krof-desktop` is a Pop!_OS 24.04 desktop used for both gaming and homelab workloads.
- Kubernetes is single-node K3s installed directly on the host.
- Argo CD manages Kubernetes desired state from this repository using an app-of-apps layout.
- GitHub `main` is the desired-state source of truth.
- Development and administration normally happen from a separate laptop.
- Private application access uses Tailscale. Do not add public exposure or public port forwarding unless explicitly requested.
- The desktop is not guaranteed to be powered on continuously. Do not assume temporary unreachability means GitOps configuration is broken.
- Preserve the host's gaming role. Avoid unnecessary daemons, resource-heavy defaults, disruptive reboots, or GPU changes.

## Working rules

1. Inspect the current branch, worktree, relevant manifests, and recent repository conventions before editing.
2. Preserve unrelated user changes. Never reset, overwrite, or reformat unrelated work.
3. Prefer one focused branch and pull request per logical change.
4. Prefer declarative GitOps changes over persistent manual cluster mutations.
5. Use direct `kubectl` changes only for bootstrap, diagnostics, recovery, or explicitly documented exceptions.
6. For risky host, storage, credential, or networking changes, verify the live state before acting and provide a rollback path.
7. Do not merge a pull request or perform destructive cleanup unless explicitly requested.

## Kubernetes and GitOps

- Preserve the existing Argo CD app-of-apps design under `kubernetes/clusters/krof-desktop/`.
- Reuse the repository's existing Kustomize layout and conventions.
- Argo CD automated sync, pruning, and self-healing mean a merged manifest can change the live cluster automatically.
- Treat resources annotated or configured with `Prune=false`, `Delete=false`, or `Retain` as intentionally protected data.
- Do not change retained storage, PVC/PV bindings, mount paths, or reclaim policy as incidental cleanup.
- Tailscale Ingress is the normal private application ingress mechanism. Traefik is currently internal-only (`ClusterIP`).
- Before cluster-side diagnostics from a development machine, verify the active kube context instead of assuming it targets `krof-desktop`.

## Secrets

This is a public repository.

Never commit:

- passwords, tokens, OAuth client secrets, API keys, private keys, or kubeconfigs
- SOPS age private identities
- plaintext Kubernetes Secret values
- Terraform/OpenTofu state
- private Tailscale addresses or tailnet DNS names
- personal information or other sensitive infrastructure details

Public age recipients beginning with `age1` are not secret. SOPS-encrypted secret material may be committed only after the repository's SOPS workflow is implemented and the resulting file is verified to contain ciphertext.

At present, sensitive Kubernetes secrets such as the Tailscale operator OAuth credential and Immich database password are bootstrap exceptions kept outside Git. Migrating their management must preserve the existing credential values unless rotation is explicitly requested. Secret-management migration and credential rotation are separate operations.

## Storage and backups

- Immich persistent data uses retained local storage on `/mnt/data-drive-2tb`.
- The local backup target is `/mnt/backup`.
- Immich backup automation is host-level and uses Restic plus a PostgreSQL dump.
- Never assume a path is mounted correctly merely because the directory exists. Validate mountpoints/filesystems before storage operations.
- Do not delete or recreate Immich PVs, PVCs, database data, media data, Restic repositories, or backup credentials without explicit approval.
- The backup drive is inside the same desktop and is not a substitute for off-machine disaster recovery.

## Validation

Use repository-pinned tools from `mise.toml` rather than inventing unrelated tool versions.

For Kubernetes manifest changes, run:

```bash
mise exec -- ./scripts/validate-kubernetes.sh
```

For OpenTofu/Terragrunt changes, run the relevant formatting/validation already used by the repository, including:

```bash
mise exec -- tofu fmt -check -recursive
mise exec -- terragrunt hcl fmt --check
```

For every change, run:

```bash
git diff --check
```

Run additional focused checks when the changed component provides them. If validation cannot run because the host or cluster is offline, say so explicitly instead of claiming the change is verified.

## Definition of done

Before handing off a change:

- review the complete diff for scope and accidental secret exposure
- confirm relevant validation passed, or clearly state what could not be run
- confirm GitOps resources are connected to the appropriate Argo CD application when applicable
- summarize operational impact and any required manual/bootstrap step
- use a draft pull request by default unless the user asks otherwise

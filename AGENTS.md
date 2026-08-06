# Homelab agent instructions

## Scope

These instructions apply to the entire repository.

Before making changes, read the relevant repository files, plus:

- `SECURITY.md` for public-repository safety rules.
- `CONTRIBUTING.md` for the contribution workflow.
- `docs/architecture.md` for the current system design.
- the relevant validation workflow, script, and pinned tool definitions for the component being changed.

Treat the tracked manifests, scripts, workflows, and current branch state as authoritative. Documentation and conversation history provide context, but they must not override the implementation when they differ.

## Operating model

- `krof-desktop` is an operator-described Pop!_OS 24.04 desktop used for both gaming and homelab workloads. Verify live host facts before risky changes.
- Kubernetes is single-node K3s installed directly on the host.
- Argo CD manages Kubernetes desired state from GitHub `main` using an app-of-apps layout.
- A merge to `main` can automatically affect Argo-managed Kubernetes resources. It does not automatically install host files, apply OpenTofu/Terragrunt, create secrets, configure Tailscale, or provision K3s and storage.
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
6. Do not run `tofu apply`, `terragrunt apply`, state/backend mutations, or persistent host installation unless the user explicitly requests the operation. Review the plan, live target, credentials, and rollback path first.
7. For risky host, storage, credential, networking, or repository-governance changes, verify the live state before acting and provide a rollback path.
8. Do not merge a pull request or perform destructive cleanup unless explicitly requested.

## Kubernetes and GitOps

- Preserve the Argo CD app-of-apps design under `kubernetes/clusters/krof-desktop/` and reuse the existing Kustomize layout.
- K3s installation, the first Argo CD installation, and the initial `cluster-root` Application are manual bootstrap boundaries; they are not reconciled into existence by this repository alone.
- Argo CD automated sync, pruning, and self-healing mean a merged manifest can change the live cluster automatically.
- Treat resources annotated or configured with `Prune=false`, `Delete=false`, or `Retain` as intentionally protected data.
- Do not change retained storage, PVC/PV bindings, node affinity, mount paths, capacities, or reclaim policy as incidental cleanup.
- `immich-storage` and `immich` are separate child Applications without explicit sync-wave ordering. During bootstrap or recovery, verify the static PVs and PVCs are ready before relying on Immich.
- Tailscale Ingress is the normal private application ingress mechanism. Traefik is currently internal-only (`ClusterIP`).
- Before cluster-side diagnostics from a development machine, verify the active kube context instead of assuming it targets `krof-desktop`.

## Secrets and external trust

This is a public repository.

Never commit:

- passwords, tokens, OAuth client secrets, API keys, private keys, or kubeconfigs
- plaintext Kubernetes Secret values or host credential files
- Terraform/OpenTofu state or plan files containing sensitive values
- private Tailscale addresses, full tailnet DNS names, or access-control configuration that reveals private identities
- personal information, unredacted application data, or other sensitive infrastructure details

Generic Kubernetes resource names, public repository URLs, required storage paths, and other deliberately tracked non-secret configuration are not credentials. Do not remove or obscure existing required configuration as incidental security cleanup; evaluate questionable identifiers against `SECURITY.md` and ask before broadening what the public repository exposes.

Current sensitive dependencies kept outside Git include:

- the Tailscale operator OAuth Secret
- the Immich database Secret
- the Restic password file
- credentials used by the GitHub provider and Azure state backend

The repository supports SOPS-encrypted Kubernetes Secret manifests through
KSOPS. Public age recipients and SOPS ciphertext may be committed; age private
identities may not. When handling encrypted Secrets:

- never write plaintext into the repository or print decrypted/base64 values
- use a mode-`0700` temporary directory outside the worktree and clean it up
- preserve existing live values unless credential rotation is explicitly requested
- verify SOPS ciphertext status and perform silent byte-for-byte comparisons
- keep re-encryption, age-recipient changes, and application credential rotation
  as distinct operations

Tailscale ACLs or grants, tag ownership, DNS and certificate behavior, OAuth provisioning, and host Tailscale configuration are external to this repository. Do not infer their live state from the Kubernetes manifests.

## Storage and backups

- Immich library and PostgreSQL data use retained local storage under `/mnt/data-drive-2tb`, bound to `krof-desktop`.
- The local Restic target is `/mnt/backup`; verify that it is the expected independent storage device rather than trusting the directory name.
- Immich backup automation is host-level and uses Restic plus a PostgreSQL dump. Repository files are not automatically copied into systemd or `/usr/local/sbin` after merge.
- Never assume a path is mounted correctly merely because the directory exists. Validate the mountpoint, filesystem, and expected device identity before storage operations.
- Do not delete or recreate Immich PVs, PVCs, database data, media data, Restic repositories, or backup credentials without explicit approval.
- The timer is persistent. A missed scheduled backup can run after the desktop next boots, so consider gaming and interactive workload impact when changing backup behavior.
- The backup script is coupled to the Immich namespace, PostgreSQL pod and container names, database name, host paths, K3s binary, Restic repository, and password location. Review and update the Kubernetes and host artifacts together when any of these change.
- The backup covers the Immich library and a generated PostgreSQL dump, not the reproducible machine-learning cache. `restic check` is not a restore test.
- There is no tested cold-restore procedure or off-machine backup in this repository. Do not describe the deployment as fully recoverable without a successful restore drill and independent secret recovery.

## Validation

Use repository-pinned tools from `mise.toml`. The scripts and GitHub Actions workflows are authoritative when validation prose elsewhere is incomplete.

For Kubernetes manifest changes, run:

```bash
mise exec -- ./scripts/validate-kubernetes.sh
```

This renders manifests and validates schemas without contacting a live cluster.
It requires network access for the remote Argo CD manifest and schema catalogs.
Without `SOPS_AGE_KEY_FILE`, production secret Kustomizations are not rendered;
the script instead verifies ciphertext and runs a disposable KSOPS smoke test.
Full production-secret validation requires the protected age identity and must
never expose its decrypted output.

For OpenTofu/Terragrunt changes, mirror `.github/workflows/iac-validation.yml`:

```bash
mise exec -- tofu fmt -check -recursive
mise exec -- terragrunt hcl fmt --check
mise exec -- tofu -chdir=infrastructure/modules/github-repository init -backend=false
mise exec -- tofu -chdir=infrastructure/modules/github-repository validate
(cd infrastructure/live && mise exec -- terragrunt hcl validate)
```

For host backup changes, at minimum run:

```bash
bash -n host/krof-desktop/backup/immich/immich-restic-backup
```

Check whitespace errors in the worktree, index, and complete pull-request range as applicable:

```bash
git diff --check
git diff --cached --check
git diff --check origin/main...HEAD
```

Run additional focused checks when the changed component provides them. If validation cannot run, state the exact missing tool, network dependency, unavailable live target, or other blocker instead of claiming the change is verified.

## Definition of done

Before handing off a change:

- review the complete branch, staged, and unstaged diff for scope and accidental secret exposure
- confirm relevant validation passed, or clearly state what could not be run
- confirm Kubernetes resources are connected to the appropriate Argo CD Application when applicable
- distinguish automatic reconciliation from required manual apply, bootstrap, installation, or secret steps
- summarize operational impact, rollback, and any live-state assumptions
- use a draft pull request by default unless the user asks otherwise

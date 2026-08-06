# Contributing

This is a personal homelab repository, but suggestions and corrections are
welcome.

## Workflow

1. Create a branch from `main`.
2. Make one focused change.
3. Do not include secrets or private infrastructure details.
4. Run the relevant validation commands.
5. Open a pull request.

## Validation

Install and use the versions declared in `mise.toml`.

For Kubernetes changes, run:

```bash
mise exec -- ./scripts/validate-kubernetes.sh
```

Public CI does not hold the production age identity. Without
`SOPS_AGE_KEY_FILE`, the validation script checks that production secret files
are encrypted, exercises SOPS and KSOPS with a disposable key, and skips only
the production secret Kustomizations. Maintainers with the production identity
must run the same command with `SOPS_AGE_KEY_FILE` set before merging an
encrypted-secret change.

For infrastructure changes, mirror the IaC workflow:

```bash
mise exec -- tofu fmt -check -recursive
mise exec -- terragrunt hcl fmt --check
mise exec -- tofu -chdir=infrastructure/modules/github-repository init -backend=false
mise exec -- tofu -chdir=infrastructure/modules/github-repository validate
(cd infrastructure/live && mise exec -- terragrunt hcl validate)
```

For every change, run:

```bash
git diff --check
```

## Encrypted Kubernetes secrets

- Never create a plaintext Secret file in the worktree, even temporarily.
- Keep the production age identity outside Git and pass its path through
  `SOPS_AGE_KEY_FILE`.
- Create or edit only files ending in `.sops.yaml` under `kubernetes/` so the
  repository creation rule applies.
- Use protected temporary files outside the repository when importing an
  existing live Secret, and remove them immediately after silent comparison.
- Confirm `sops filestatus <file>` reports encrypted status before committing.
- Treat `sops updatekeys` or re-encryption as separate from rotating the
  application credential stored inside the file.

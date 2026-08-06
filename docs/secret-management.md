# Kubernetes secret management

Kubernetes Secrets may be stored in this public repository only as SOPS
ciphertext. SOPS encrypts the Secret values for a dedicated age recipient, and
KSOPS decrypts the resources while Argo CD renders their Kustomizations.

This document covers the encryption foundation and its operational boundary.
It does not authorize credential rotation or deletion.

## Trust and custody

- `.sops.yaml` contains only the public `age1...` recipient.
- The corresponding age identity must have an independent off-machine recovery
  copy and must never be committed.
- Argo CD receives the identity through the manually bootstrapped
  `argocd/sops-age` Secret under the `keys.txt` key.
- GitHub Actions does not receive the production identity.
- The repo-server runs reviewed Kustomize exec plugins. A malicious change
  merged to a trusted source repository could execute in that component.

The cluster copy is not a backup. Losing every off-cluster identity makes the
encrypted repository content unrecoverable.

## Bootstrap

Verify the active kube context and target cluster before creating the bootstrap
Secret. Create it from the protected identity without printing a YAML manifest:

```bash
kubectl create secret generic sops-age \
  --namespace argocd \
  --from-file=keys.txt="$SOPS_AGE_KEY_FILE" \
  --dry-run=client \
  --output yaml |
kubectl apply --filename -
```

Bootstrap `sops-age` before allowing the Argo CD repo-server patch to reconcile.
Otherwise the replacement pod cannot mount its required volume. Verify the
Secret key exists without retrieving its contents, then confirm the repo-server
rollout and KSOPS init container succeeded.

## Editing encrypted files

Use the pinned tools and keep the identity path outside the repository:

```bash
export SOPS_AGE_KEY_FILE=/protected/path/homelab-krof-desktop.age
mise exec -- sops kubernetes/path/to/secret.sops.yaml
mise exec -- sops filestatus kubernetes/path/to/secret.sops.yaml
mise exec -- ./scripts/validate-kubernetes.sh
```

When importing a live Secret, use a mode-`0700` temporary directory, redirect
all exports to files, strip cluster-generated metadata, encrypt directly to the
final `.sops.yaml` path, and compare the decrypted `.data` objects silently.
Never put plaintext or a base64 value in the worktree or command output.

## Validation model

With `SOPS_AGE_KEY_FILE`, validation decrypts and schema-checks every secret
Kustomization. Without it, validation:

1. rejects tracked age private identities and plaintext Secret manifests
2. requires every `.sops.yaml` file to report encrypted status
3. exercises SOPS, age, KSOPS, Kustomize, and kubeconform with a disposable key
4. skips only production Kustomizations that reference encrypted files

The public path proves ciphertext policy and tool integration, but it cannot
verify a production file's MAC or decrypted Kubernetes schema.

## Recovery and rotation

If KSOPS prevents manifest generation, revert dependent secret Applications
before removing the repo-server integration. Retained Secrets must not be
pruned during that rollback. Keep the age bootstrap Secret until no Application
depends on it; deleting it is a separate destructive action.

Use `sops updatekeys` when intentionally changing recipients. Re-encrypting a
file or changing its age recipient does not rotate the Tailscale OAuth client,
Immich database password, or any other application credential.

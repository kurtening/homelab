#!/usr/bin/env bash

set -euo pipefail

for required_command in age-keygen git ksops kubeconform kustomize sops; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    echo "Required command not found: $required_command" >&2
    exit 127
  fi
done

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

render_dir="$(mktemp -d)"
trap 'rm -rf -- "$render_dir"' EXIT

kubernetes_schema_version="${KUBERNETES_SCHEMA_VERSION:-1.36.0}"
schema_catalog='https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'

validate_render() {
  local directory="$1"
  local output="$2"

  if [[ ! -s "$output" ]]; then
    echo "Rendered output is empty: $directory" >&2
    exit 1
  fi

  echo "Validating: $directory"

  kubeconform \
    -strict \
    -summary \
    -skip CustomResourceDefinition \
    -kubernetes-version "$kubernetes_schema_version" \
    -schema-location default \
    -schema-location "$schema_catalog" \
    "$output"
}

private_identity_pattern='AGE''-SECRET-KEY-'
while IFS= read -r -d '' repository_file; do
  if [[ -f "$repository_file" ]] && grep -Iq . "$repository_file" &&
    grep -q "$private_identity_pattern" "$repository_file"; then
    echo "Age private identity detected: $repository_file" >&2
    exit 1
  fi
done < <(git ls-files --cached --others --exclude-standard -z)

while IFS= read -r -d '' kubernetes_manifest; do
  if grep -q -E '^kind:[[:space:]]+Secret[[:space:]]*$' "$kubernetes_manifest" &&
    [[ "$kubernetes_manifest" != *.sops.yaml ]]; then
    echo "Plaintext Kubernetes Secret manifest detected: $kubernetes_manifest" >&2
    exit 1
  fi
done < <(
  find kubernetes -type f -name '*.yaml' -print0 | sort -z
)

while IFS= read -r -d '' encrypted_file; do
  echo "Checking ciphertext: $encrypted_file"

  if ! file_status="$(sops filestatus "$encrypted_file")"; then
    echo "Unable to inspect SOPS file: $encrypted_file" >&2
    exit 1
  fi

  if ! grep -q '"encrypted"[[:space:]]*:[[:space:]]*true' <<<"$file_status"; then
    echo "SOPS file is not encrypted: $encrypted_file" >&2
    exit 1
  fi
done < <(find kubernetes -type f -name '*.sops.yaml' -print0 | sort -z)

smoke_dir="$render_dir/ksops-smoke"
mkdir -p "$smoke_dir"

age-keygen -o "$smoke_dir/keys.txt" >/dev/null 2>&1
smoke_recipient="$(age-keygen -y "$smoke_dir/keys.txt")"

cat >"$smoke_dir/secret.yaml" <<'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: ksops-smoke
  namespace: default
type: Opaque
stringData:
  value: disposable-test-value
EOF

SOPS_AGE_RECIPIENTS="$smoke_recipient" sops encrypt \
  --encrypted-regex '^(data|stringData)$' \
  "$smoke_dir/secret.yaml" >"$smoke_dir/secret.sops.yaml"

cat >"$smoke_dir/secret-generator.yaml" <<'EOF'
apiVersion: viaduct.ai/v1
kind: ksops
metadata:
  name: ksops-smoke
  annotations:
    config.kubernetes.io/function: |
      exec:
        path: ksops
files:
  - secret.sops.yaml
EOF

cat >"$smoke_dir/kustomization.yaml" <<'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

generators:
  - secret-generator.yaml
EOF

echo "Rendering disposable KSOPS smoke test"
SOPS_AGE_KEY_FILE="$smoke_dir/keys.txt" kustomize build \
  --enable-alpha-plugins \
  --enable-exec \
  "$smoke_dir" >"$smoke_dir/rendered.yaml"
validate_render "disposable KSOPS smoke test" "$smoke_dir/rendered.yaml"

found=0

while IFS= read -r -d '' kustomization; do
  found=1

  directory="$(dirname "$kustomization")"
  safe_name="${directory//\//_}"
  output="$render_dir/${safe_name}.yaml"

  if grep -R -q --include='*.yaml' '\.sops\.yaml' "$directory" &&
    [[ -z "${SOPS_AGE_KEY_FILE:-}" ]]; then
    echo "Skipping encrypted render without SOPS_AGE_KEY_FILE: $directory"
    continue
  fi

  echo "Rendering: $directory"

  kustomize build \
    --enable-alpha-plugins \
    --enable-exec \
    "$directory" >"$output"

  validate_render "$directory" "$output"
done < <(
  find kubernetes \
    -type f \
    -name kustomization.yaml \
    -print0 |
    sort -z
)

if [[ "$found" -eq 0 ]]; then
  echo "No kustomization.yaml files found under kubernetes/" >&2
  exit 1
fi

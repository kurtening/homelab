#!/usr/bin/env bash

set -euo pipefail

for required_command in git kubectl kubeconform; do
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

found=0

while IFS= read -r -d '' kustomization; do
  found=1

  directory="$(dirname "$kustomization")"
  safe_name="${directory//\//_}"
  output="$render_dir/${safe_name}.yaml"

  echo "Rendering: $directory"

  kubectl kustomize "$directory" >"$output"

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

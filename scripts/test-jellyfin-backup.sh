#!/usr/bin/env bash
set -euo pipefail

# Exercise the production freshness gate without host paths or Restic access.
repo_root="$(git rev-parse --show-toplevel)"
test_dir="$(mktemp -d /tmp/jellyfin-backup-test.XXXXXX)"
trap 'find "$test_dir" -type f -delete; rmdir "$test_dir"' EXIT
BUILTIN_BACKUPS_PATH="$test_dir"
source <(sed -n '/^has_recent_builtin_backup() {$/,/^}$/p' \
  "$repo_root/host/krof-desktop/backup/jellyfin/jellyfin-restic-backup")

if has_recent_builtin_backup; then
  echo "Empty directory was accepted" >&2
  exit 1
fi

printf 'unfinished archive' >"$test_dir/partial.zip"
if has_recent_builtin_backup; then
  echo "Invalid ZIP was accepted" >&2
  exit 1
fi

printf 'disposable archive fixture' >"$test_dir/fixture.txt"
(cd "$test_dir" && zip -q valid.zip fixture.txt)
has_recent_builtin_backup

touch -d '3 hours ago' "$test_dir/valid.zip"
if has_recent_builtin_backup; then
  echo "Stale ZIP was accepted" >&2
  exit 1
fi

echo "Jellyfin archive freshness and integrity checks passed"

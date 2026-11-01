# Predictable maintenance

Maintenance is an operator-run monthly review, **not a new timer, bot, daemon or
automatic upgrade policy**. Prefer the first convenient idle window each month,
in Asia/Manila, after a completed backup cycle. The desktop can remain a gaming
machine; an intentional power-off is not a deployment failure.

## Recorded inventory and update ownership

[Recorded versions](versions.md) is generated from tracked non-secret sources:
application/monitoring images and digests, upstream Argo release, Tailscale chart,
Minecraft/Fabric/mod/client pins, development tools, workflow Actions, validation
Python package and the live-stack provider lockfile. Check it without network:

```bash
python3 -m venv /tmp/homelab-maintenance-tools
/tmp/homelab-maintenance-tools/bin/pip install -r scripts/requirements-monitoring.txt
/tmp/homelab-maintenance-tools/bin/python scripts/maintenance-inventory --check
```

Use an existing reviewed venv when available. After an intentional source update,
run the generator with `--write` and review the resulting `docs/versions.md` diff.
Stage newly added source files first: only tracked paths are inventoried, so
untracked caches and experimental files cannot silently enter the public table.
Do not update this generated table instead of its source definitions. CI checks
that it is current. Generation needs Python 3.11+ and the pinned PyYAML package;
it does not query registries, download images, read Secrets or suggest versions.

Dependabot currently proposes weekly **GitHub Actions and Terraform dependency**
updates only. It does not maintain app-image pins, the Tailscale chart, Argo
bundle, Minecraft compatibility set, `mise.toml`, OS packages or host scripts.
The provider consumer lockfile lives under the Terragrunt live stack: inspect it
alongside any module constraint update; a changed constraint alone is not proof
that the live provider selection was refreshed. Never apply infrastructure just
because its validation passed.

The current inventory intentionally exposes pinning boundaries: `whoami` and
workflow Actions use tags rather than immutable digests/commit SHAs. Kustomize's
monitoring aliases resolve to the explicit image digests; do not count aliases
as additional unpinned images. Upstream Argo/chart dependencies and Tailscale
proxy images require separate inspection. Record pin-hardening work as a separate
reviewed change, not an incidental upgrade in this PR.

## Monthly operator checklist

1. **Read health before changing it.** Confirm the intended kube context and
   desktop reachability; review Argo/workloads, mounts, enabled backup timers,
   collector freshness, installed-script/unit drift and active alerts. Use the
   read-only status command once its separate PR is merged. Offline/access gaps
   remain PENDING. Do not automatically repair drift or suppress unknown history.
2. **Review real backup/recovery evidence.** Check the latest genuine scheduled
   chains for all three apps, including source integrity and snapshot inclusion,
   not just service exit codes. Keep snapshot IDs, timer/invocation evidence and
   Jellyfin cycle identifiers in the private ledger. Never increment its seven-
   cycle hold because a calendar week passed. Separate file recovery, restored
   content/startup, application acceptance and full host-loss recovery.
3. **Review disk and resource trends.** Inspect data/backup/root filesystem space
   and inodes, Restic growth, retained drill sizes, and monitoring's three-day
   metrics/24-hour log retention. PVC requests are not quotas. Confirm monitoring
   stays within its existing memory/CPU budget during idle/gaming. Do not prune,
   move storage or raise limits just to clear warnings.
4. **Review official security/release notices.** Compare recorded versions with
   upstream release notes/advisories for K3s/Kubernetes, Argo, Tailscale, apps,
   monitoring and host backup tools. Assess exposure and compatibility, including
   private-only access and the gaming host's constraints; a newer tag is not an
   automatic upgrade instruction. Keep detailed private configuration out of
   public issues. If no update is needed, record that decision and review date.
5. **Review credential recovery access, not values.** Check vault access and
   custody of separate app Restic passwords, age identity, Grafana administrator,
   K3s token/private configuration and external-provider/Tailscale recovery.
   Verify existing candidates through protected workflows when necessary.
   Presence of a file/Secret is not independent custody. No routine rotation,
   password regeneration or secret export is authorized by this checklist.
6. **Choose one focused maintenance PR.** Take the highest-impact justified fix
   or update, not a mass upgrade. Record official release/compatibility sources,
   exact old/new versions/digests, resource/storage impact, validation, required
   manual host steps and rollback prerequisites. A public summary includes only
   redacted outcomes; retain detailed inventories locally outside Git.

## Upgrade and delivery gates

Application upgrades remain separate draft PRs. Verify current backups and
independent recovery credentials, rehearse migrations on restored copies, and
agree a maintenance window before stopping writers. Immich server/ML versions
move together; retain compatible PostgreSQL/extensions and Valkey unless a
separate reviewed migration requires otherwise. Its rollback restores a compatible
database/library checkpoint; reverting images cannot undo schema migrations.

Jellyfin upgrades preserve its shared SQLite/retained-storage migration contract;
never start stopped Compose against a running Kubernetes instance. Minecraft
updates review server/Fabric/mod/client compatibility together and need a world
checkpoint. Monitoring updates must retain its privacy, retention, notification
and gaming resource gates; do not upgrade the Tailscale operator incidentally.
K3s/host updates require their own maintenance/recovery plan, not an application
image PR. No broad package upgrade is part of this routine's implementation.

Mirror relevant tests/validation and the full PR diff review. Merging affects
Argo-managed resources only: host units/scripts, providers/state and external
trust still need explicit reviewed operations. Leave merging to the operator.
After a reviewed update verify workload/content behavior, private access and a
subsequent successful backup before declaring acceptance. Keep failed state and
diagnostics until exact cleanup targets are reviewed.

## Cleanup, limitations and review record

Cleanup is a separate proposal: record exact directories/container/network IDs,
allocated size, ownership, nested mounts and dependencies; distinguish failed
attempts from successful evidence. Re-check those facts immediately before any
approved removal. Exclude production data, PVs/PVCs, Restic repositories,
credentials, Docker images and stopped Compose. Preserve successful drills and
the previous installed backup script until separately approved. No broad Docker
pruning, implicit deletion or cleanup timer.

Keep a private record with review date, reviewed Git revision, desktop online/
offline state, PASS/PENDING/FAIL gates, latest verified snapshot/cycle identifiers,
resource/disk observations, upstream notices reviewed and next operator action.
Publish only durable redacted facts; do not commit raw logs, vault data, personal
media or private endpoints. Off-machine backups remain deferred for dedicated
hardware; a full isolated desktop-loss drill and measured recovery objectives
remain unproven. This checklist creates no extra schedules or external service.

# Minecraft console candidate assessment

This is an evaluation, not an activation approval. No candidate below has been
validated against the production world or granted Tailscale access. Require
separate co-admin identities, authenticated RCON, private ingress, documented
recovery, supported dependencies, and a reviewable deployment before adoption.

## Existing draft

The `itzg/rcon:0.14.1-1` draft uses Node 12 and salted MD5 password hashing.
Its first-command RCON callback required a local patch. The legacy console is
not recommended for activation; the admin draft's security gate remains pending.

## MineDash

[MineDash](https://github.com/Avalin/MineDash) revision
`d60ecdf852694c66d1acc23158e0c99450486423` offers individual users, RCON and
bcrypt on .NET 10. In an isolated, resource-limited container with synthetic
credentials and no published ports, an unauthenticated client registered the
initial account, and a second independent unauthenticated client successfully
registered another account. This does not satisfy a selected-co-admin-only
account model without an additional verified restriction. At review on
2026-11-11, GitHub reported no published releases or repository license. The
container was not connected to the live cluster or production data.

## mc-admin

[mc-admin](https://github.com/tekikaito/mc-admin) revision
`c2882d40d4493b1c490e2a5c2777999c1e96863a` supports Discord OAuth identities
and an optional user-ID allowlist. Its README documents `DISCORD_OAUTH_ENABLED`,
while its code reads `ENABLE_DISCORD_OAUTH`; authentication defaults to disabled.
In a disposable Go test, setting only the documented flag left a protected test
route accessible without authentication. The same test verified that the actual
flag enables configuration validation when OAuth settings are missing. An empty
allowlist permits any Discord user to authenticate. The candidate has not passed
an end-to-end OAuth, authorization, RCON, recovery or image-supply-chain review;
GitHub reported no repository license at review. The Go test ran in a disposable,
resource-limited container without any production credentials or cluster access.
Do not activate it based on this assessment.

## Recommendation

Do not deploy either candidate or the legacy draft yet. Continue evaluating a
maintained, licensed console that has explicit per-user administration and a
fail-closed authentication configuration. Avoid candidates that require the
host Docker socket: this server runs in K3s, and granting that socket introduces
an unrelated host-control boundary. Discord notifications remain a separate
change and do not require selecting a console.

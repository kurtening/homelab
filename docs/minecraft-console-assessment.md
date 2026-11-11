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
allowlist permits any Discord user to authenticate. A second isolated Go test
using the actual flag and a synthetic two-user allowlist verified that anonymous
requests redirect to login, an invalid OAuth state is rejected, and the session
cookie has Secure and HttpOnly flags for an HTTPS callback. It did not exercise
Discord itself or verify allowlist enforcement after the OAuth exchange.

The upstream Dockerfile uses unpinned Go 1.25 and Alpine 3.20 base images. This
revision has no repository license and has not been reviewed for current Go
compatibility or dependencies. The candidate has not passed an end-to-end OAuth,
authorization, RCON, recovery or image-supply-chain review;
GitHub reported no repository license at review. The Go test ran in a disposable,
resource-limited container without any production credentials or cluster access.
Do not activate it based on this assessment.

## MCRCON

[MCRCON](https://github.com/bySenom/MCRCON) revision
`b34a26ca0311cf64f6612734e875fc5d01e15ed9` advertises multiple users and bcrypt.
Source inspection found that its registration route has no authentication
middleware and forwards a requester-supplied role to account creation, which
accepts `admin`. This is a source-level finding, not a runtime exploitation
test. It makes the candidate unsuitable for the requested selected-admin access
without remediation and verification; do not deploy it.

## MC Admin Panel

[MC Admin Panel](https://github.com/mitchsurp/mcadmin) revision
`ff668e9b92b98ea802c9f813ecc87907e255f49b` supports Minecraft RCON, but source
inspection found command handlers exposed through Socket.IO and HTTP without an
authentication check. GitHub reported no repository license at review. This was
a source review rather than a runtime penetration test. It does not provide the
required individual Discord identities and is not a candidate for deployment.

## Minecraft WebUI

[Minecraft WebUI](https://github.com/picardflo/minecraft_webui) revision
`2da196624bb8a391fea34a8f9ff1850a2184a667` is MIT-licensed and connects via
RCON. Source inspection found a single shared administrator password and a
shared session identity; the session cookie also lacks the Secure flag. It does
not provide the required individual Discord identities. This was a source review,
not a runtime authentication test, and it is not a candidate for deployment.

## Recommendation

Do not deploy these candidates or the legacy draft yet. Continue evaluating a
maintained, licensed console that has explicit per-user administration and a
fail-closed authentication configuration. Avoid candidates that require the
host Docker socket: this server runs in K3s, and granting that socket introduces
an unrelated host-control boundary. Discord notifications remain a separate
change and do not require selecting a console.

# Security Policy

## Scope

This repository contains configuration for a personal homelab and is
published primarily for learning and documentation.

The following should never be committed:

- passwords, tokens, API keys, or private keys
- Terraform or OpenTofu state
- Tailscale authentication material
- SOPS age private keys
- private hostnames, addresses, or personal information
- unredacted application configuration containing credentials

SOPS-encrypted Kubernetes manifests and public age recipients beginning with
`age1` may be committed. Before committing an encrypted manifest, verify that
SOPS reports it as encrypted and that no age identity or plaintext value appears
in the diff. Encryption is not credential rotation; exposed credentials must be
rotated separately.

## Reporting a Security Issue

Do not open a public issue containing sensitive information.

Report suspected exposed credentials or security-sensitive configuration
using GitHub's private vulnerability reporting feature:

1. Open the repository's **Security** tab.
2. Select **Advisories**.
3. Select **Report a vulnerability**.

If the report concerns an exposed credential, identify the affected file
and commit, but do not reproduce the credential in a public issue.

## Supported Configuration

Only the current configuration on the `main` branch is maintained.
Historical examples and older commits are not supported releases.

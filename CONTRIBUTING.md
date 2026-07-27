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

For infrastructure changes, run:

```bash
tofu fmt -check -recursive
terragrunt hcl fmt --check
locals {
  github_owner = "kurtening"
}

generate "github_provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"

  contents = <<EOF
provider "github" {
  owner = "${local.github_owner}"
}
EOF
}

generate "backend" {
  path      = "backend.tf"
  if_exists = "overwrite_terragrunt"

  contents = <<EOF
terraform {
  backend "azurerm" {
    storage_account_name = "prdtfstatesa"
    container_name       = "tfstate"
    key                  = "${path_relative_to_include()}/tofu.tfstate"

    subscription_id  = "2e2cb1de-d5a7-457f-bb58-0da3bf975f88"
    use_azuread_auth = true
    use_cli          = true
  }
}
EOF
}
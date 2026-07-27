include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../modules/github-repository"
}

inputs = {
  repository_name = "homelab"
  description     = "GitOps-managed personal homelab infrastructure"
  visibility      = "public"
}
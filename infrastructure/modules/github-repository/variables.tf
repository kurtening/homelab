variable "repository_name" {
  description = "Name of the GitHub repository."
  type        = string
}

variable "description" {
  description = "Description shown on GitHub."
  type        = string
  default     = "GitOps-managed personal homelab infrastructure"
}

variable "visibility" {
  description = "Repository visibility."
  type        = string
  default     = "public"

  validation {
    condition     = contains(["public", "private"], var.visibility)
    error_message = "Visibility must be public or private."
  }
}
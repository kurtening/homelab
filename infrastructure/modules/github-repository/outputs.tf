output "repository_name" {
  description = "GitHub repository name."
  value       = github_repository.this.name
}

output "html_url" {
  description = "GitHub repository URL."
  value       = github_repository.this.html_url
}

output "ssh_clone_url" {
  description = "SSH clone URL."
  value       = github_repository.this.ssh_clone_url
}
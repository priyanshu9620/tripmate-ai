output "url" {
  description = "Public URL (http, ALB DNS)"
  value       = "http://${aws_lb.app.dns_name}"
}
output "ecr_repository" {
  value = aws_ecr_repository.app.repository_url
}
output "instance_id" {
  value = aws_instance.app.id
}
output "target_group_arn" {
  value = aws_lb_target_group.app.arn
}
output "github_deploy_access_key_id" {
  description = "GitHub Actions secret AWS_ACCESS_KEY_ID"
  value       = aws_iam_access_key.github_deploy.id
}
output "github_deploy_secret_access_key" {
  description = "GitHub Actions secret AWS_SECRET_ACCESS_KEY (tofu output -raw …)"
  value       = aws_iam_access_key.github_deploy.secret
  sensitive   = true
}

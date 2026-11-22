output "site_url" {
  description = "HTTPS address of the static site (CloudFront)."
  value       = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "site_bucket" {
  description = "Bucket that `arena export s3` uploads the built site to."
  value       = aws_s3_bucket.site.bucket
}

output "api_url" {
  description = "HTTP address of the REST API (load balancer)."
  value       = "http://${aws_lb.api.dns_name}"
}

output "ecr_repository_url" {
  description = "Where to push the API image."
  value       = aws_ecr_repository.api.repository_url
}

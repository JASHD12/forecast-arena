variable "region" {
  description = "AWS region (eu-central-1 is Frankfurt, close to the German data sources)."
  type        = string
  default     = "eu-central-1"
}

variable "name_prefix" {
  description = "Prefix of every resource name."
  type        = string
  default     = "forecast-arena"
}

variable "api_image" {
  description = "Container image of the REST API, for example <account>.dkr.ecr.<region>.amazonaws.com/forecast-arena-api:<tag>. The Dockerfile in the repository builds it."
  type        = string
}

variable "api_desired_count" {
  description = "Number of API tasks (0 switches the service off without destroying it)."
  type        = number
  default     = 1
}

variable "budget_limit_usd" {
  description = "Monthly cost budget in US dollars; an email is sent at 80 percent of it."
  type        = number
  default     = 10
}

variable "budget_email" {
  description = "Address that receives the budget alarm."
  type        = string
}

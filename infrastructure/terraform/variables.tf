variable "aws_region" {
  description = "AWS deployment region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "suits-compliance"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r6g.xlarge"
}

variable "ecs_task_cpu" {
  description = "ECS Task CPU allocation"
  type        = number
  default     = 2048
}

variable "ecs_task_memory" {
  description = "ECS Task Memory allocation (MB)"
  type        = number
  default     = 4096
}

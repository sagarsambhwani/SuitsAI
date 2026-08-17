terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ==========================================
# 1. Networking (VPC & Subnets)
# ==========================================
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-1"
  }
}

resource "aws_subnet" "private_1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "${var.aws_region}a"

  tags = {
    Name = "${var.project_name}-private-1"
  }
}

# ==========================================
# 2. S3 Immutable Document Lake
# ==========================================
resource "aws_kms_key" "s3_key" {
  description             = "KMS Key for Compliance Document Lake"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_s3_bucket" "document_lake" {
  bucket = "${var.project_name}-document-lake-${var.environment}"
}

resource "aws_s3_bucket_versioning" "lake_versioning" {
  bucket = aws_s3_bucket.document_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake_encryption" {
  bucket = aws_s3_bucket.document_lake.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3_key.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# ==========================================
# 3. RDS PostgreSQL (pgvector enabled)
# ==========================================
resource "aws_db_instance" "postgres" {
  identifier          = "${var.project_name}-postgres"
  engine              = "postgres"
  engine_version      = "16.1"
  instance_class      = var.db_instance_class
  allocated_storage   = 100
  storage_type        = "gp3"
  storage_encrypted   = true
  kms_key_id          = aws_kms_key.s3_key.arn
  username            = "compliance_admin"
  password            = "ChangeThisSecurePasswordInProduction123!"
  skip_final_snapshot = true

  tags = {
    Name = "${var.project_name}-rds-pgvector"
  }
}

# ==========================================
# 4. SQS Ingestion Queue (Phase 1 Eventing)
# ==========================================
resource "aws_sqs_queue" "ingestion_dlq" {
  name = "${var.project_name}-ingestion-dlq"
}

resource "aws_sqs_queue" "ingestion_queue" {
  name                      = "${var.project_name}-ingestion-queue"
  message_retention_seconds = 86400
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingestion_dlq.arn
    maxReceiveCount     = 3
  })
}

# ==========================================
# 5. ECS Fargate Cluster & Service
# ==========================================
resource "aws_ecs_cluster" "app_cluster" {
  name = "${var.project_name}-cluster"
}

resource "aws_iam_role" "ecs_execution_role" {
  name = "${var.project_name}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_ecs_task_definition" "api_task" {
  family                   = "${var.project_name}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = "123456789012.dkr.ecr.${var.aws_region}.amazonaws.com/${var.project_name}:latest"
    essential = true
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
    }]
    environment = [
      { name = "ENVIRONMENT", value = var.environment },
      { name = "DEFAULT_LLM_PROVIDER", value = "bedrock" },
      { name = "BEDROCK_REGION", value = var.aws_region }
    ]
  }])
}

output "rds_endpoint" {
  description = "RDS PostgreSQL Endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "document_lake_bucket" {
  description = "S3 Document Lake Bucket Name"
  value       = aws_s3_bucket.document_lake.id
}

output "sqs_ingestion_queue_url" {
  description = "SQS Ingestion Queue URL"
  value       = aws_sqs_queue.ingestion_queue.id
}

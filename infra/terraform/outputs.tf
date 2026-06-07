output "region" {
  value = data.aws_region.current.name
}

output "s3_raw_bucket" {
  description = "Raw archive bucket name."
  value       = aws_s3_bucket.raw.bucket
}

output "rds_endpoint" {
  description = "RDS host:port."
  value       = aws_db_instance.main.endpoint
}

output "rds_address" {
  description = "RDS hostname only."
  value       = aws_db_instance.main.address
}

output "rds_port" {
  value = aws_db_instance.main.port
}

output "rds_db_name" {
  value = aws_db_instance.main.db_name
}

output "ec2_instance_id" {
  description = "Airflow host instance id (use with `aws ssm start-session`)."
  value       = aws_instance.airflow.id
}

output "ec2_public_ip" {
  value = aws_instance.airflow.public_ip
}

output "ssm_session_command" {
  description = "Open a shell on the Airflow host with no SSH key."
  value       = "aws ssm start-session --region ${var.region} --target ${aws_instance.airflow.id}"
}

output "psql_connection_template" {
  description = "psql connection string (fill in the master password)."
  value       = "psql 'host=${aws_db_instance.main.address} port=${aws_db_instance.main.port} dbname=${aws_db_instance.main.db_name} user=${var.db_master_username} sslmode=require'"
}

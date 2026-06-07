resource "aws_db_subnet_group" "main" {
  name       = "${var.name_prefix}-db-subnets"
  subnet_ids = aws_subnet.public[*].id
  tags       = { Name = "${var.name_prefix}-db-subnets" }
}

# Parameter group that forces TLS. Connect with sslmode=require (see README/profiles).
resource "aws_db_parameter_group" "main" {
  name        = "${var.name_prefix}-pg16"
  family      = "postgres16"
  description = "Force SSL for ${var.name_prefix}"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_db_instance" "main" {
  identifier     = "${var.name_prefix}-pg"
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  db_name  = var.db_name
  username = var.db_master_username
  password = var.db_master_password
  port     = 5432

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = 0 # disable storage autoscaling (cost control)
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = var.db_publicly_accessible
  parameter_group_name   = aws_db_parameter_group.main.name

  multi_az                     = false
  backup_retention_period      = 1
  auto_minor_version_upgrade   = true
  apply_immediately            = true
  deletion_protection          = false # demo project; flip to true for anything real
  skip_final_snapshot          = true  # demo project; allows clean `terraform destroy`
  performance_insights_enabled = false # not supported on db.t4g.micro

  tags = { Name = "${var.name_prefix}-pg" }
}

# EC2 (Airflow host) security group.
# No inbound is required for SSM Session Manager. SSH (22) is opened ONLY if
# ssh_allowed_cidrs is non-empty.
resource "aws_security_group" "ec2" {
  name        = "${var.name_prefix}-ec2"
  description = "Airflow host: egress all; optional SSH from allowlist"
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "All outbound (S3, Alpha Vantage, package mirrors, SSM)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-ec2" }
}

resource "aws_security_group_rule" "ec2_ssh" {
  count             = length(var.ssh_allowed_cidrs) > 0 ? 1 : 0
  type              = "ingress"
  description       = "SSH from allowlist"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = var.ssh_allowed_cidrs
  security_group_id = aws_security_group.ec2.id
}

# RDS security group: Postgres 5432 reachable from the EC2 host SG and from any
# explicitly allowlisted CIDRs (your laptop, and later Hex egress IPs).
resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds"
  description = "Postgres 5432 from EC2 SG + allowlisted CIDRs"
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-rds" }
}

resource "aws_security_group_rule" "rds_from_ec2" {
  type                     = "ingress"
  description              = "Postgres from the Airflow EC2 host"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.ec2.id
  security_group_id        = aws_security_group.rds.id
}

resource "aws_security_group_rule" "rds_from_cidrs" {
  count             = length(var.db_allowed_cidrs) > 0 ? 1 : 0
  type              = "ingress"
  description       = "Postgres from allowlisted CIDRs (laptop / Hex)"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  cidr_blocks       = var.db_allowed_cidrs
  security_group_id = aws_security_group.rds.id
}

variable "region" {
  description = "AWS region. us-east-1 is cheapest and free-tier friendly."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix for all resource names/tags."
  type        = string
  default     = "equities-analytics"
}

variable "tags" {
  description = "Extra tags applied to every resource (merged with defaults)."
  type        = map(string)
  default     = {}
}

# ---------------------------------------------------------------------------
# Networking (dedicated NAT-free VPC)
# ---------------------------------------------------------------------------
variable "vpc_cidr" {
  description = "CIDR block for the project VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs (>= 2, in distinct AZs — required by the RDS subnet group)."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

# ---------------------------------------------------------------------------
# RDS Postgres
# ---------------------------------------------------------------------------
variable "db_name" {
  description = "Initial database name created in RDS."
  type        = string
  default     = "equities"
}

variable "db_master_username" {
  description = "RDS master username (admin). The dbt app role is created separately via bootstrap.sql."
  type        = string
  default     = "postgres"
}

variable "db_master_password" {
  description = "RDS master password. Set in terraform.tfvars (gitignored) or via TF_VAR_db_master_password."
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class. db.t4g.micro = cheapest Graviton, free-tier eligible."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_engine_version" {
  description = "Postgres major.minor version. Leave major only (e.g. \"16\") to let AWS pick the latest minor."
  type        = string
  default     = "16"
}

variable "db_allocated_storage" {
  description = "RDS storage in GB (20 GB is the free-tier ceiling)."
  type        = number
  default     = 20
}

variable "db_publicly_accessible" {
  description = "Whether RDS gets a public IP. Needed for Hex (SaaS) and laptop psql; locked down by db_allowed_cidrs."
  type        = bool
  default     = true
}

variable "db_allowed_cidrs" {
  description = "CIDRs allowed to reach Postgres 5432 (e.g. your laptop \"x.x.x.x/32\"). The EC2 host is always allowed via its SG."
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# EC2 (Airflow host)
# ---------------------------------------------------------------------------
variable "ec2_instance_type" {
  description = "EC2 instance type for the self-hosted Airflow host."
  type        = string
  default     = "t3.small"
}

variable "ec2_key_name" {
  description = "Optional existing EC2 key pair name for SSH. Leave null to use SSM Session Manager only (recommended)."
  type        = string
  default     = null
}

variable "ssh_allowed_cidrs" {
  description = "CIDRs allowed to SSH (22). Leave empty to disable SSH entirely and use SSM Session Manager."
  type        = list(string)
  default     = []
}

variable "ec2_root_volume_gb" {
  description = "EC2 root EBS volume size in GB."
  type        = number
  default     = 20
}

# ---------------------------------------------------------------------------
# Budget + notifications
# ---------------------------------------------------------------------------
variable "budget_amount" {
  description = "Monthly cost budget (USD) that triggers an alert."
  type        = number
  default     = 25
}

variable "budget_notification_email" {
  description = "Email to receive budget alerts."
  type        = string
  default     = "jphillips@usserviceanimals.org"
}

variable "enable_sns" {
  description = "Create an SNS topic and grant the EC2 role publish rights (optional Airflow failure alerts)."
  type        = bool
  default     = false
}

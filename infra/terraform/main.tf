provider "aws" {
  region = var.region

  default_tags {
    tags = merge(
      {
        Project   = var.name_prefix
        ManagedBy = "terraform"
      },
      var.tags,
    )
  }
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# Use the account's default VPC + subnets. A custom VPC with private subnets
# would require a NAT gateway (~$32/mo) and blow the <$50/mo budget. Security
# is enforced via tight security groups instead (see security_groups.tf).
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

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

# Networking lives in a dedicated, NAT-free VPC — see vpc.tf.

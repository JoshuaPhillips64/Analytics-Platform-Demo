terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Local state by default. NOTE: state contains the RDS master password in
  # plaintext, so terraform.tfstate is gitignored. For a team/stretch setup,
  # switch to an encrypted S3 backend (see infra/README.md).
}

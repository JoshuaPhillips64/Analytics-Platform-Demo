# Latest Amazon Linux 2023 AMI (x86_64) via the public SSM parameter.
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

locals {
  # Bootstrap the host for Phase 6: Docker + compose plugin + git. The SSM agent
  # is preinstalled on AL2023, so Session Manager works out of the box.
  user_data = <<-EOF
    #!/bin/bash
    set -euxo pipefail
    dnf update -y
    dnf install -y docker git
    systemctl enable --now docker
    usermod -aG docker ec2-user
    # Docker Compose v2 plugin
    mkdir -p /usr/libexec/docker/cli-plugins
    curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
      -o /usr/libexec/docker/cli-plugins/docker-compose
    chmod +x /usr/libexec/docker/cli-plugins/docker-compose
  EOF
}

resource "aws_instance" "airflow" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.ec2_instance_type
  subnet_id                   = aws_subnet.public[0].id
  iam_instance_profile        = aws_iam_instance_profile.ec2.name
  vpc_security_group_ids      = [aws_security_group.ec2.id]
  key_name                    = var.ec2_key_name
  associate_public_ip_address = true
  user_data                   = local.user_data

  # Enforce IMDSv2 (token-required) for instance metadata.
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_size = var.ec2_root_volume_gb
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "${var.name_prefix}-airflow" }
}

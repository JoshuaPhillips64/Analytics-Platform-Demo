# IAM instance role for the EC2 Airflow host. No static keys anywhere
# (golden rule #10): the host uses this role via the instance metadata service.
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${var.name_prefix}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
  tags               = { Name = "${var.name_prefix}-ec2-role" }
}

# Least-privilege S3 access scoped to the raw bucket only.
data "aws_iam_policy_document" "s3_access" {
  statement {
    sid       = "ListRawBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.raw.arn]
  }
  statement {
    sid       = "ReadWriteRawObjects"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.raw.arn}/*"]
  }
}

resource "aws_iam_role_policy" "s3_access" {
  name   = "${var.name_prefix}-s3-access"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.s3_access.json
}

# SSM Session Manager: shell access with no SSH key and no inbound port.
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Optional SNS publish rights for Airflow failure alerts.
resource "aws_iam_role_policy" "sns_publish" {
  count = var.enable_sns ? 1 : 0
  name  = "${var.name_prefix}-sns-publish"
  role  = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "PublishAlerts"
      Effect   = "Allow"
      Action   = "sns:Publish"
      Resource = aws_sns_topic.alerts[0].arn
    }]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.name_prefix}-ec2-profile"
  role = aws_iam_role.ec2.name
}

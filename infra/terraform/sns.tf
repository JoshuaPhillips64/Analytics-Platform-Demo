# Optional SNS topic for Airflow on_failure alerts (wired up in Phase 6).
resource "aws_sns_topic" "alerts" {
  count = var.enable_sns ? 1 : 0
  name  = "${var.name_prefix}-alerts"
  tags  = { Name = "${var.name_prefix}-alerts" }
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.enable_sns ? 1 : 0
  topic_arn = aws_sns_topic.alerts[0].arn
  protocol  = "email"
  endpoint  = var.budget_notification_email
}

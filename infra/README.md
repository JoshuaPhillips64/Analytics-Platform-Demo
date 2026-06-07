# Infrastructure (Terraform)

Phase 1 provisions all AWS infra as code: an S3 raw-archive bucket, an RDS
Postgres `db.t4g.micro`, an EC2 `t3.small` Airflow host with an **IAM instance
role** (no static keys), least-privilege security groups, and a **$25 AWS Budget
alert**. You run `terraform plan` / `apply`; nothing here spends money until you do.

## Design decisions (and why)
- **Dedicated NAT-free VPC.** A small VPC (`vpc.tf`) with two public subnets across
  AZs + an internet gateway. No NAT gateway (that's ~$32/mo and would break the
  <$50/mo rule). RDS/EC2 sit in public subnets, secured by tight security groups,
  not network topology.
- **SSM Session Manager, not SSH.** The EC2 role attaches `AmazonSSMManagedInstanceCore`,
  so you get a shell with **no key pair and no inbound port 22**. SSH is opt-in via
  `ssh_allowed_cidrs`.
- **No static AWS keys** (golden rule #10). The host reaches S3 through its instance
  role; the S3 policy is scoped to the raw bucket only.
- **TLS enforced on RDS** via `rds.force_ssl=1` — always connect with `sslmode=require`.
- **DB schemas/role created via `psql`**, not Terraform, so `apply` never depends on
  in-cluster DB networking. It's pure DDL (`infra/sql/bootstrap.sql`).

## Prerequisites
- Terraform >= 1.6 and the AWS CLI v2 installed locally.
- AWS credentials configured (`aws configure` / SSO) for an account where you can
  create S3/RDS/EC2/IAM/Budgets resources.
- The **Session Manager plugin** for the AWS CLI (for `aws ssm start-session`).

## 1. Configure
```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set db_master_password and db_allowed_cidrs (your /32).
curl -s https://checkip.amazonaws.com   # <- your public IP for db_allowed_cidrs
```

## 2. Plan & apply
```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out tfplan
terraform apply tfplan
```
Capture the outputs (bucket name, RDS endpoint, instance id):
```bash
terraform output
```

## 3. Bootstrap the database (schemas + dbt role)
RDS takes a few minutes to become available. Then, from a machine whose IP is in
`db_allowed_cidrs` (your laptop). Pass the dbt password as a RAW value (no
surrounding quotes) — psql quotes it safely via `format(%L, ...)`.

**PowerShell (Windows):**
```powershell
$RDS_ADDR = terraform output -raw rds_address
$env:PGPASSWORD = "<your db_master_password>"   # else psql prompts for it
psql "host=$RDS_ADDR port=5432 dbname=equities user=postgres sslmode=require" `
  -v dbt_password="DBTP4SS%#" `
  -f ../sql/bootstrap.sql
```

**bash/zsh (macOS/Linux):**
```bash
RDS_ADDR=$(terraform output -raw rds_address)
psql "host=$RDS_ADDR port=5432 dbname=equities user=postgres sslmode=require" \
  -v dbt_password='DBTP4SS%#' \
  -f ../sql/bootstrap.sql
```
Save the dbt password — Phase 3 puts it in the dbt `profiles.yml`, never in git.

## 4. Verify the Phase 1 GATE

**PowerShell (Windows):**
```powershell
# (a) psql connects and the four schemas exist
psql "host=$RDS_ADDR port=5432 dbname=equities user=postgres sslmode=require" -c '\dn'
#  -> expect: raw, staging, intermediate, marts (owned by dbt)

# (b) EC2 reaches S3 via its instance role, with NO static keys
$INSTANCE_ID = terraform output -raw ec2_instance_id
$BUCKET      = terraform output -raw s3_raw_bucket
aws ssm start-session --target $INSTANCE_ID
#   then ON the instance (Linux shell):
#   aws sts get-caller-identity     # shows the assumed-role ARN, not a user key
#   aws s3 ls s3://<BUCKET>         # succeeds (empty listing is fine)
#   exit

# (c) Budget alert active
$ACCT = aws sts get-caller-identity --query Account --output text
aws budgets describe-budgets --account-id $ACCT `
  --query "Budgets[?BudgetName=='equities-analytics-monthly'].BudgetLimit"
```
(bash: replace `$VAR = ...` with `VAR=$(...)` and backticks with `\`.)

Gate passes when (a) shows four schemas, (b) `aws s3 ls` works from the role, and
(c) the budget exists.

## 5. Stop when idle (cost discipline)
This is a couple-of-days project — **stop RDS and EC2 whenever you're not building
or demoing** (golden rule #6):
```bash
aws rds stop-db-instance --db-instance-identifier equities-analytics-pg
aws ec2 stop-instances --instance-ids <INSTANCE_ID>
# restart:
aws rds start-db-instance --db-instance-identifier equities-analytics-pg
aws ec2 start-instances --instance-ids <INSTANCE_ID>
```
RDS auto-restarts after 7 days stopped — just stop it again. (Alternative for $0:
run Airflow locally in Docker per `orchestration/` and skip the EC2 entirely.)

## 6. Tear down everything
```bash
terraform destroy
```

## Cost note
| Resource | Idle | 24/7 |
|---|---|---|
| S3 (raw, <1 GB) | ~$0 | ~$0 |
| RDS db.t4g.micro (20 GB gp3) | $0 stopped | ~$12–15 + storage |
| EC2 t3.small | ~$0 stopped | ~$15 |
| VPC networking (IGW, no NAT) | $0 | $0 |
| Budget alert | $0 | $0 |

Free-tier eligible accounts pay ~$0; otherwise <$10/mo if you stop instances,
~$30 worst case 24/7 — comfortably under $50.

## Optional: remote state (stretch)
For team use, move state to an encrypted S3 backend (+ DynamoDB lock table) by
adding a `backend "s3"` block to `versions.tf` and re-running `terraform init`.
Local state is fine for a solo portfolio build and is gitignored (it contains the
DB password).

# TripMate AI on AWS: one EC2 instance running the compose stack (api + Postgres) behind an Application Load
# Balancer, image from ECR, secrets from SSM Parameter Store, a scoped IAM user for GitHub Actions deploys.
#
# Every resource carries a one-line "what / why". Region + account: the free-plan project (SCP-limited to
# ap-southeast-2; OIDC provider creation is denied there, hence the IAM user — see notes P-22 in ShopEase).
# Create:  make infra-plan && make infra-apply      Destroy (after every session): make infra-destroy
# ---------------------------------------------------------------------------------------------------------
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.82.2"
    }
  }
}

provider "aws" {
  region  = var.region
  profile = var.profile
  default_tags {
    tags = { Project = "tripmate-ai", ManagedBy = "opentofu" }
  }
}

# ---- network: the region's default VPC (public subnets in 3 AZs); a custom VPC + NAT would cost ~$35/month ----
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# latest Amazon Linux 2023 AMI via the public SSM parameter, so it never goes stale
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_caller_identity" "me" {}

# ---- security groups = the firewall: internet → ALB:80 only; ALB → instance:8000 only; no SSH (use SSM) ----
resource "aws_security_group" "alb" {
  name        = "tripmate-alb"
  description = "ALB: HTTP from the internet"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "app" {
  name        = "tripmate-app"
  description = "App instance: 8000 from the ALB only"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ---- ECR: the private registry CI pushes to and the instance pulls from with its IAM role ----
resource "aws_ecr_repository" "app" {
  name                 = "tripmate-ai"
  image_tag_mutability = "MUTABLE" # :latest moves; CI also pushes immutable :<sha> tags
  force_delete         = true      # destroy removes images too, so teardown is one command
}

# ---- secrets + config: SSM SecureString (free); the instance reads /tripmate/* at every deploy ----
locals {
  params = {
    LLM_PROVIDER      = var.llm_provider
    LLM_MODEL         = var.llm_model
    GOOGLE_API_KEY    = var.google_api_key
    LANGSMITH_TRACING = var.langsmith_api_key != "" ? "true" : "false"
    LANGSMITH_API_KEY = var.langsmith_api_key
    LANGSMITH_PROJECT = "tripmate-ai-aws"
    TOOLS_MODE        = var.tools_mode
  }
}

resource "aws_ssm_parameter" "app" {
  for_each = local.params
  name     = "/tripmate/${each.key}"
  type     = "SecureString"
  value    = each.value == "" ? "-" : each.value # SSM rejects empty values; "-" is filtered out on the instance
}

# ---- IAM for the instance: SSM Session Manager/Run Command, pull from ECR, read /tripmate/* params ----
resource "aws_iam_role" "instance" {
  name = "tripmate-instance"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "instance_ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "instance" {
  name = "tripmate-instance"
  role = aws_iam_role.instance.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Resource = aws_ecr_repository.app.arn },
      { Effect = "Allow", Action = ["ssm:GetParameters", "ssm:GetParametersByPath"], Resource = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.me.account_id}:parameter/tripmate/*" },
    ]
  })
}

resource "aws_iam_instance_profile" "instance" {
  name = "tripmate-instance"
  role = aws_iam_role.instance.name
}

# ---- the instance: api + Postgres via docker compose; Postgres data on the root volume (short-lived stack) ----
resource "aws_instance" "app" {
  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = var.instance_type
  subnet_id              = sort(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.instance.name
  user_data = templatefile("${path.module}/user-data.sh", {
    region    = var.region
    ecr_url   = aws_ecr_repository.app.repository_url
    image_tag = var.image_tag
  })
  user_data_replace_on_change = true
  credit_specification {
    cpu_credits = "unlimited" # a burstable instance that runs out of credits stalls; unlimited costs cents
  }
  root_block_device {
    volume_size = 16
  }
  depends_on = [aws_ssm_parameter.app]
  tags       = { Name = "tripmate-app", Role = "app" }
}

# ---- ALB → target group (health /healthz) → listener :80 ----
resource "aws_lb" "app" {
  name               = "tripmate"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids
  idle_timeout       = 300 # an agent turn with a real model can exceed the 60 s default (P-14)
}

resource "aws_lb_target_group" "app" {
  name                 = "tripmate-app"
  port                 = 8000
  protocol             = "HTTP"
  vpc_id               = data.aws_vpc.default.id
  deregistration_delay = 15
  health_check {
    path                = "/healthz"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
    matcher             = "200"
  }
}

resource "aws_lb_target_group_attachment" "app" {
  target_group_arn = aws_lb_target_group.app.arn
  target_id        = aws_instance.app.id
  port             = 8000
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# ---- GitHub Actions deploy identity: scoped IAM user (OIDC provider creation is denied by the SCP) ----
resource "aws_iam_user" "github_deploy" {
  name = "tripmate-github-deploy"
}

resource "aws_iam_access_key" "github_deploy" {
  user = aws_iam_user.github_deploy.name
}

resource "aws_iam_user_policy" "github_deploy" {
  name = "tripmate-github-deploy"
  user = aws_iam_user.github_deploy.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      { Effect = "Allow", Action = ["ecr:*"], Resource = aws_ecr_repository.app.arn },
      { Effect = "Allow", Action = ["ec2:DescribeInstances", "elasticloadbalancing:DescribeTargetHealth", "elasticloadbalancing:DescribeTargetGroups", "elasticloadbalancing:DescribeLoadBalancers"], Resource = "*" },
      { Effect = "Allow", Action = ["ssm:SendCommand"], Resource = ["arn:aws:ssm:${var.region}::document/AWS-RunShellScript", "arn:aws:ec2:${var.region}:${data.aws_caller_identity.me.account_id}:instance/*"] },
      { Effect = "Allow", Action = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"], Resource = "*" },
    ]
  })
}

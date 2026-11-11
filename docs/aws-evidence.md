# AWS deployment evidence (2026-11-11)

Stack: `infra/` (OpenTofu), region ap-southeast-2, 26 resources (`tofu state list`). Created by the user with
`make infra-apply`; destroyed with `make infra-destroy` after the session.

| what | evidence |
|---|---|
| CD pipeline | GitHub Actions run https://github.com/priyanshu9620/tripmate-ai/actions/runs/43032175539 — build linux/amd64 → ECR `:<sha>` + `:latest` → SSM `deploy.sh` → ALB target healthy. Build+push+deploy ≈ 2 min. |
| Public URL | `http://tripmate-2106406734.ap-southeast-2.elb.amazonaws.com` (ALB → 1 × t3.micro, api + Postgres via compose) |
| `/healthz` through the ALB | `{"version":"0.1.0","llm_provider":"google_genai","tools_mode":"live","memory":"postgres","postgres":true}` |
| Real conversation on AWS | thread `b3bc7417e28f`: Delhi→Goa 4 days 2 people ₹60,000 → proposal; approve → `done`, references `1FBF28, 1409DA, 79BCA7`, total ₹46,870; `GET /trips` → 1 trip in the AWS Postgres |
| `/ui` | HTTP 200 |

Found and fixed on the first deploy (notes P-14, P-15): the first agent turn took 61 s with live tools and the ALB
cut the HTTP response at its 60 s default idle timeout (the graph finished server-side; approve still worked) →
`idle_timeout = 300`; the deploy user lacked `elasticloadbalancing:DescribeLoadBalancers` for the smoke step.

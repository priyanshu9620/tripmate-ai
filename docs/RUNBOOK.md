# Runbook — bring TripMate up on AWS before a demo, tear it down after

Normal days: nothing runs on AWS (cost ₹0). The resume claim is proven by [`aws-evidence.md`](aws-evidence.md).
This page is for the day you want a live public URL. Total: ~8 minutes up, ~3 minutes down, ≈ $1 (₹80) per day while up.

## Before (≈ 8 min)
```
cd ~/Desktop/tripmate
git pull                                                     # latest main
SECRETS_PASSPHRASE='<passphrase>' make secrets-unpack        # only on a fresh laptop (restores .env, tfvars, tfstate)
make infra-plan && make infra-apply                          # ≈ 3 min; creates EC2 + ALB + ECR + SSM + IAM (22 resources)
gh auth switch -u priyanshu9620
gh secret set AWS_ACCESS_KEY_ID     --repo priyanshu9620/tripmate-ai --body "$(tofu -chdir=infra output -raw github_deploy_access_key_id)"
gh secret set AWS_SECRET_ACCESS_KEY --repo priyanshu9620/tripmate-ai --body "$(tofu -chdir=infra output -raw github_deploy_secret_access_key)"
gh variable set AWS_DEPLOY_ENABLED  --repo priyanshu9620/tripmate-ai --body true
gh workflow run deploy --repo priyanshu9620/tripmate-ai      # ≈ 2.5 min: build → ECR → SSM deploy → ALB healthy → smoke
gh run watch --repo priyanshu9620/tripmate-ai                 # wait for green
tofu -chdir=infra output -raw url                            # → http://tripmate-….ap-southeast-2.elb.amazonaws.com
```
Check: `curl <url>/healthz` shows `"memory":"postgres"`; open `<url>/ui` and run one request
(first reply 20–60 s). Share `<url>/ui`.

Why the secrets step every time: `make infra-destroy` deletes the deploy IAM user, so apply creates a new key.

## During
- Demo script and what to say: [`../DEMO.md`](../DEMO.md). Live tools are on (`TOOLS_MODE=live` in `infra/variables.tf`).
- A push to `main` auto-deploys while `AWS_DEPLOY_ENABLED=true`. Don't push half-done work during a demo.
- Gemini free tier ≈ 500 requests/day; one conversation ≈ 7. LangSmith traces land in project `tripmate-ai-aws`.

## After (≈ 3 min)
```
gh variable set AWS_DEPLOY_ENABLED --repo priyanshu9620/tripmate-ai --body false   # pushes stop trying to deploy
make infra-destroy                                                                 # type yes; ≈ 2 min
SECRETS_PASSPHRASE='<passphrase>' make secrets-pack && git add secrets.tar.enc && git commit -m "chore: secrets" && git push
```
Verify nothing bills:
```
AWS_PROFILE=shopease AWS_REGION=ap-southeast-2 aws ec2 describe-instances --filters Name=instance-state-name,Values=running --query 'length(Reservations[].Instances[])'
AWS_PROFILE=shopease AWS_REGION=ap-southeast-2 aws elbv2 describe-load-balancers --query 'length(LoadBalancers)'
```
Both must print `0`.

## If something is off
| symptom | do |
|---|---|
| `tofu init` hangs | provider mirror in `~/.tofurc` (see ShopEase notes P-20) |
| apply fails on IAM/OIDC | expected for OIDC (SCP); the stack uses an IAM user, nothing to do |
| deploy workflow skipped | `AWS_DEPLOY_ENABLED` is not `true` |
| deploy red at "Deploy through SSM" | instance still booting: wait 2 min, `gh workflow run deploy` again |
| `/healthz` says `memory: memory` | Postgres container not healthy yet; wait, or SSM into the box: `docker compose -f /opt/tripmate/docker-compose.yml logs` |
| reply empty after ~60 s | ALB idle timeout is 300 s in `infra/main.tf`; if you lowered it, raise it |
| `git push` rejected | work credential helper; see `GUIDE.md` §6 for the token one-off |

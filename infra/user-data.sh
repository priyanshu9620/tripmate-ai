#!/bin/bash
# Boot script (Amazon Linux 2023): Docker + compose plugin, /opt/tripmate/{docker-compose.yml,deploy.sh}.
# deploy.sh <tag> = secrets from SSM → .env, pull the image from ECR, `docker compose up -d`.
# CI calls deploy.sh through SSM Run Command on every push to main. First boot tries :latest and tolerates
# "image not found" (the first CI deploy fills ECR).
set -euxo pipefail
dnf install -y docker
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

mkdir -p /opt/tripmate
cat > /opt/tripmate/docker-compose.yml <<'YML'
services:
  postgres:
    image: postgres:16.4-alpine
    environment: { POSTGRES_USER: tm, POSTGRES_PASSWORD: tm, POSTGRES_DB: tripmate }
    volumes: [ "tm-pgdata:/var/lib/postgresql/data" ]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tm -d tripmate"]
      interval: 5s
      timeout: 3s
      retries: 10
    restart: unless-stopped
  api:
    image: "$${IMAGE}"
    env_file: .env
    environment:
      DATABASE_URL: postgresql://tm:tm@postgres:5432/tripmate
      APP_INSTANCE: "$${INSTANCE_ID}"
    ports: [ "8000:8000" ]
    depends_on:
      postgres: { condition: service_healthy }
    restart: unless-stopped
    logging: { driver: json-file, options: { max-size: "20m", max-file: "3" } }
volumes:
  tm-pgdata:
YML

cat > /opt/tripmate/deploy.sh <<'EOF2'
#!/bin/bash
set -euo pipefail
TAG="$${1:-latest}"
REGION="${region}"
ECR="${ecr_url}"
cd /opt/tripmate
# secrets/config → .env (SecureString params under /tripmate/; "-" means unset)
aws ssm get-parameters-by-path --region "$REGION" --path /tripmate/ --with-decryption \
  --query 'Parameters[].[Name,Value]' --output text \
  | awk -F'\t' '$2 != "-" { sub(".*/", "", $1); print $1 "=" $2 }' > .env
chmod 600 .env
# IMDSv2 (token first — AL2023 requires it) → instance id, exposed to the app as APP_INSTANCE
TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
export INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id || hostname)
export IMAGE="$ECR:$TAG"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$${ECR%%/*}"
docker compose pull api
docker compose up -d --remove-orphans   # recreates only the api container when its image changed; Postgres stays
docker image prune -f >/dev/null
EOF2
chmod +x /opt/tripmate/deploy.sh
/opt/tripmate/deploy.sh "${image_tag}" || echo "first boot: no image in ECR yet — the first CI deploy will start the app"

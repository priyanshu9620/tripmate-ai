#!/bin/bash
# Pack/unpack the git-ignored secret files into ONE encrypted archive that is committed to the repo, so a fresh
# clone + one passphrase restores everything. AES-256 via openssl (present on every Mac/Linux).
#   SECRETS_PASSPHRASE=... scripts/secrets.sh pack     → secrets.tar.enc
#   SECRETS_PASSPHRASE=... scripts/secrets.sh unpack   → restores the files below in place
set -euo pipefail
FILES=(.env infra/terraform.tfvars infra/terraform.tfstate infra/terraform.tfstate.backup infra/.terraform.lock.hcl aws-credentials)
cd "$(dirname "$0")/.."
: "${SECRETS_PASSPHRASE:?set SECRETS_PASSPHRASE}"
case "${1:-}" in
  pack)
    # snapshot the AWS profile the infra uses, so a fresh laptop gets it back (restored to ./aws-credentials; copy into ~/.aws)
    aws configure export-credentials --profile shopease --format env-no-export 2>/dev/null | sed 's/^/# /' > /dev/null || true
    { echo "[shopease]"; echo "aws_access_key_id = $(aws configure get aws_access_key_id --profile shopease)"; echo "aws_secret_access_key = $(aws configure get aws_secret_access_key --profile shopease)"; } > aws-credentials
    present=(); for f in "${FILES[@]}"; do [ -f "$f" ] && present+=("$f"); done
    tar -czf - "${present[@]}" | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:SECRETS_PASSPHRASE -out secrets.tar.enc
    rm -f aws-credentials
    echo "packed ${#present[@]} files → secrets.tar.enc ($(wc -c < secrets.tar.enc) bytes): ${present[*]}" ;;
  unpack)
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:SECRETS_PASSPHRASE -in secrets.tar.enc | tar -xzf - -v ;;
  list)
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:SECRETS_PASSPHRASE -in secrets.tar.enc | tar -tzf - ;;
  *) echo "usage: secrets.sh pack|unpack|list"; exit 2 ;;
esac

# Fresh laptop → working TripMate + a Claude session that knows everything

This repo carries the code, the measured results, the project notes (`notes/`), the Claude memory note
(`notes/claude-memory/`) and the secrets as one encrypted archive (`secrets.tar.enc`). Nothing lives only on a laptop.

## 1. Tools (macOS; Linux equivalents in brackets)
```
brew install uv docker tofu awscli gh git        # [apt: docker.io, uv via curl, opentofu, awscli, gh]
uv python install 3.11
```
Docker Desktop must be running. `gh auth login` with the personal account `priyanshu9620`.

## 2. Clone and restore
```
git clone https://github.com/priyanshu9620/tripmate-ai ~/Desktop/tripmate && cd ~/Desktop/tripmate
git config user.name "Priyanshu Gupta" && git config user.email "guptapriyanshu1822@gmail.com"
SECRETS_PASSPHRASE='<the passphrase>' make secrets-unpack   # restores .env, infra/terraform.tfvars, infra/*.tfstate*
uv sync && make up && make test                                # api + postgres on :8000, 24 tests
ln -s ~/Desktop/tripmate/notes ~/Desktop/tripmate-notes         # optional: same path the notes refer to
```
AWS: `~/.aws/credentials` needs the `[shopease]` profile (the free-plan project key). It is in the archive too
(`notes/aws-credentials.example` says the format); copy it into `~/.aws/credentials`.

## 3. Start a Claude Code session that resumes the work
Open Claude Code in `~/Desktop/tripmate` and paste:

> Read notes/BOOTSTRAP.md, then notes/session/HANDOFF.md, DECISIONS.md, BUILD-PLAN.md, PROGRESS.md, PROBLEMS.md
> and notes/handoff-prompt-template.md. Save notes/claude-memory/tripmate-project.md into your memory directory
> and index it in MEMORY.md. Then continue from the "Single next command" in HANDOFF.md. Same rules as the template:
> commit to main directly (D-19), never run tofu apply/destroy yourself, nothing from any employer.

## 4. Keep it portable
After every session: `make secrets-pack` if any secret/state file changed, update `notes/session/*`, copy the memory
note back into `notes/claude-memory/`, commit, push. The notes folder on the Desktop is a symlink into the repo.

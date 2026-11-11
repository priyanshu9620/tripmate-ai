# LangSmith setup (do this when Phase 2 is ready; takes 5 minutes, free tier)

1. Go to https://smith.langchain.com and sign up with your personal email (not work). Free "Developer" plan is enough (5k traces/month).
2. Left sidebar → **Settings → API Keys → Create API Key**. Name it `tripmate-local`. Copy it once; it is shown only once.
3. In `~/Desktop/tripmate/.env` add:
   ```
   LANGSMITH_TRACING=true
   LANGSMITH_API_KEY=lsv2_...
   LANGSMITH_PROJECT=tripmate-ai
   ```
   Never paste the key in chat; the `.env` is git-ignored and `.env.example` lists the three names with empty values.
4. `make up` then run one conversation (`make demo`). Open https://smith.langchain.com → Projects → `tripmate-ai`:
   each conversation turn is a trace; expand it to see supervisor → researcher → tool calls with inputs, outputs, latency and tokens.
5. For the CI/AWS deploy the same three variables go in GitHub → repo Settings → Secrets and variables → Actions
   (key as a secret, the other two as variables). Optional; the app runs without them.

What it gives you for the interview: a visual of the multi-agent run (which agent called which tool, how long, how many tokens)
and the ability to open a failed run and see the exact prompt that went wrong. "Traced and debugged agent runs with LangSmith" = this.

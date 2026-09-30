Trinity

Choose a backend with `CLAUDE_BACKEND` (or `--backend` when running `cli.py` directly):

- `api` (default): Claude API, billed to your Console account.
  `export ANTHROPIC_API_KEY=...`
- `subscription`: goes through the Claude Code CLI and uses your Claude Subscription.
   Run `claude setup-token`, then
  `export CLAUDE_BACKEND=subscription CLAUDE_CODE_OAUTH_TOKEN=<token>`.

```bash
docker compose up -d --build
docker attach "$(docker compose ps -q cli)"
```
Run prompts after compose and attach.

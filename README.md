Trinity

Choose a backend with `CLAUDE_BACKEND` (or `--backend` when running `cli.py` directly):

- `api` (default): Claude API, billed to your Console account.
  `export ANTHROPIC_API_KEY=...`
- `subscription`: goes through the Claude Code CLI and uses your Claude Subscription.
   Run `claude setup-token`, then
  `export CLAUDE_BACKEND=subscription CLAUDE_CODE_OAUTH_TOKEN=<token>`.

Choose an agent with `TRINITY_AGENT` (or `--agent`):

- `coder` calls the Coder Agent. It gets your prompt plus the past prompts and responses
  stored in the database, and uses `read_file`, `write_file`, `edit_file` and `execute_code`
  inside `./workspace` (mounted at `/workspace`). The Planner and Tester are bypassed.
- `ack`: Claude only acknowledges the prompt.

```bash
docker compose up -d --build
docker attach "$(docker compose ps -q cli)"
```
Run prompts after compose and attach.

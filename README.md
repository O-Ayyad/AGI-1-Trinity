# Trinity



## Configuration

Choose a backend with `CLAUDE_BACKEND` (or `--backend` when running `cli.py` directly):

- `api` (default): Claude API
  `export ANTHROPIC_API_KEY=...`
- `subscription`: goes through the Claude Code CLI and uses Claude subscription.
  Run `claude setup-token`, then
  `export CLAUDE_BACKEND=subscription CLAUDE_CODE_OAUTH_TOKEN=<token>`.
- `local`: any local server that speaks the OpenAI chat completions API with tool calling (Ollama, LM Studio, llama.cpp `llama-server`, vLLM). 
  Start your server, then `export CLAUDE_BACKEND=local LOCAL_MODEL=<model name>`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOCAL_BASE_URL` | `http://localhost:11434/v1` (`http://host.docker.internal:11434/v1` in Docker) | Server URL, including `/v1` |
| `LOCAL_MODEL` | `llama3.1` | Model name the server should use for every agent |
| `LOCAL_API_KEY` | empty | Sent as a bearer token when set |
| `LOCAL_TIMEOUT` | `600` | Seconds to wait for each response |

The Coder needs a model that supports tool calling. For Ollama, run `ollama pull <model>` first. Inside Docker, `localhost` is the container itself, so the default URL points at the host machine.

Choose an agent with `TRINITY_AGENT` (or `--agent`):

- `workflow` (default) runs the Planner, Coder and Tester through the orchestrator.
- `coder` calls the Coder Agent alone with your prompt plus the past prompts and responses stored in the database. The Planner and Tester are bypassed.

The Coder reads, writes, edits and executes code only inside `./workspace`. Set `CLAUDE_MODEL` to change the model.

## Run with Docker

```bash
docker compose up -d --build
docker attach "$(docker compose ps -q cli)"
```

Or run `python run.py`, which does both and stops the container on exit. Type prompts after attaching.

## Run locally

```bash
pip install -r requirements.txt
python main.py
```

Prompt history is kept in `data/context.db`. Use `--history` to print it and `--reset` to clear it.

## Tests

```bash
python -m unittest discover -s tests -t .
```

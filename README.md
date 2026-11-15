# Trinity

A multi-agent coding assistant. A Planner breaks your prompt into tasks, a Coder writes and runs the code inside a sandboxed workspace, and a Tester checks the result. Failed tests send feedback back to the Coder, up to two retries.

## Structure

```
.
├── main.py              entry point (used by the Docker image)
├── run.py               builds, starts and attaches to the Docker container
├── cli.py               prompt REPL, SQLite prompt history, agent selection
├── agents/
│   ├── config.py        shared backend, model and workspace settings
│   ├── ai_client.py     Claude calls for the Planner
│   ├── local_client.py  OpenAI-compatible client for local model servers
│   ├── planner_agent.py Planner Agent: task plan with validation
│   ├── coder_agent.py   Coder Agent: tool-use loop over read/write/edit/execute
│   ├── tester_agent.py  Tester Agent: PASS/FAIL feedback
│   ├── tool_layer.py    sandboxed file and code tools
│   └── coder_mcp.py     the same tools as an MCP server
├── orchestrator/        LangGraph workflow: planner -> coder -> tester -> retry/finish
├── vscode-extension/    right-click "Trinity: Run on Selection" for VS Code
├── tests/
├── Dockerfile
├── compose.yaml
├── requirements.txt
└── .env.example
```

## Configuration

Settings are read from environment variables and from a `.env` file in the project folder (copy `.env.example` to `.env`). Variables already set in your shell win over `.env`.

Choose a backend with `CLAUDE_BACKEND` (or `--backend` when running `cli.py` directly):

- `api` (default): Claude API, billed to your Console account.
  `export ANTHROPIC_API_KEY=...`
- `subscription`: goes through the Claude Code CLI and uses your Claude subscription.
  Run `claude setup-token`, then
  `export CLAUDE_BACKEND=subscription CLAUDE_CODE_OAUTH_TOKEN=<token>`.
- `local`: any local server that speaks the OpenAI chat completions API with tool calling (Ollama, LM Studio, llama.cpp `llama-server`, vLLM). No Anthropic account is needed.
  Start your server, then `export CLAUDE_BACKEND=local LOCAL_MODEL=<model name>`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOCAL_BASE_URL` | `http://localhost:11434/v1` (`http://host.docker.internal:11434/v1` in Docker) | Server URL, including `/v1`. Leave it out of `.env` when using Docker unless it points at a host the container can reach |
| `LOCAL_MODEL` | `llama3.1` | Model name the server should use for every agent |
| `LOCAL_API_KEY` | empty | Sent as a bearer token when set |
| `LOCAL_TIMEOUT` | `600` | Seconds to wait for each response |

The Coder needs a model that supports tool calling. For Ollama, run `ollama pull <model>` first. Inside Docker, `localhost` is the container itself, so the default URL points at the host machine.

Choose an agent with `TRINITY_AGENT` (or `--agent`):

- `workflow` (default) runs the Planner, Coder and Tester through the orchestrator.
- `coder` calls the Coder Agent alone with your prompt plus the past prompts and responses stored in the database. The Planner and Tester are bypassed.
- `ack`: Claude only acknowledges the prompt.

The Coder reads, writes, edits and executes code only inside `./workspace` (mounted at `/workspace` in Docker). Set `CLAUDE_MODEL` to change the model.

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

Prompt history is kept in `data/context.db`. Use `--history` to print it and `--reset` to clear it. For scripts, `--prompt-file` reads the prompt from a file and `--result-file` writes the final response to one; the exit code is non-zero when a prompt fails.

## VS Code

`vscode-extension/` adds **Trinity: Run on Selection** to the editor's right-click menu. The highlighted text is sent as the prompt, and the folder open in VS Code is the only directory the Coder may touch. See `vscode-extension/README.md` for setup.

## Tests

```bash
python -m unittest discover -s tests -t .
cd vscode-extension && npm test
```

FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir anthropic mcp langgraph

# Claude Code CLI for the "subscription" backend.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://claude.ai/install.sh | bash
ENV PATH="/root/.local/bin:${PATH}"
COPY cli.py main.py planner.py ai_client.py ./
COPY agents/ ./agents/
COPY orchestrator/ ./orchestrator/

ENV CONTEXT_DB=/data/context.db
ENV CODER_WORKDIR=/workspace
VOLUME ["/data"]

ENTRYPOINT ["python", "-u", "main.py"]

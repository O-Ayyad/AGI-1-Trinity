FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir anthropic

# Claude Code CLI for the "subscription" backend.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://claude.ai/install.sh | bash
ENV PATH="/root/.local/bin:${PATH}"
COPY cli.py main.py ./

ENV CONTEXT_DB=/data/context.db
VOLUME ["/data"]

ENTRYPOINT ["python", "-u", "main.py"]

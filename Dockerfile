FROM python:3.12-slim

WORKDIR /app
COPY cli.py main.py ./

ENV CONTEXT_DB=/data/context.db
VOLUME ["/data"]

ENTRYPOINT ["python", "-u", "main.py"]

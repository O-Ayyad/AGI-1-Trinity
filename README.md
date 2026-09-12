Trinity

```bash
docker compose up -d --build
docker attach "$(docker compose ps -q cli)"
```
Run prompts after compose and attach.

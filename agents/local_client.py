import httpx

from agents import config


class LocalModelError(RuntimeError):
    pass


def chat(messages, model=None, tools=None, max_tokens=4096):
    payload = {"model": model or config.LOCAL_MODEL, "messages": messages, "max_tokens": max_tokens}
    if tools:
        payload["tools"] = tools
    headers = {"Content-Type": "application/json"}
    if config.LOCAL_API_KEY:
        headers["Authorization"] = f"Bearer {config.LOCAL_API_KEY}"
    url = f"{config.LOCAL_BASE_URL.rstrip('/')}/chat/completions"

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=config.LOCAL_TIMEOUT)
        response.raise_for_status()
        return response.json()["choices"][0]
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip()
        raise LocalModelError(
            f"Local model server returned {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LocalModelError(f"Could not reach the local model server at {url}: {exc}") from exc
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LocalModelError("Local model server returned an unexpected response.") from exc


def complete(system_prompt, user_prompt, model=None, max_tokens=4096):
    choice = chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        max_tokens=max_tokens,
    )
    return (choice["message"].get("content") or "").strip()


def openai_tools(tool_definitions):
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in tool_definitions
    ]

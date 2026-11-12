import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

BACKENDS = ("api", "subscription")
AGENTS = ("coder", "ack")
DEFAULT_AGENT = os.environ.get("TRINITY_AGENT", "coder")
DEFAULT_BACKEND = os.environ.get("CLAUDE_BACKEND", "api")
DEFAULT_DB = os.environ.get("CONTEXT_DB", "/data/context.db")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
SYSTEM_PROMPT = (
    "You are Claude, attached to a CLI that only records prompts as context. "
    "You never fulfil, plan, or answer the user's request. Reply with a single short "
    "sentence that says you are Claude, that you understood the prompt, and that you "
    "will not act on the request. No preamble, no follow-up questions."
)


def claude_response(body, backend):
    """Ask Claude to acknowledge the prompt and return what it says."""
    if backend == "subscription":
        return subscription_response(body)
    return api_response(body)


def api_response(body):
    """Call the Claude API directly; needs ANTHROPIC_API_KEY."""
    import anthropic

    message = anthropic.Anthropic().messages.create(
        model=MODEL,
        max_tokens=1024,
        output_config={"effort": "low"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": body}],
    )
    return " ".join(
        block.text.strip() for block in message.content if block.type == "text"
    ).strip()


def subscription_response(body):
    """Go through the Claude Code CLI, which uses its logged-in Claude subscription."""
    result = subprocess.run(
        ["claude", "-p", "--model", MODEL, "--system-prompt", SYSTEM_PROMPT, "--tools", ""],
        input=body,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def connect(db_path):
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prompts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            body       TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(prompts)")}
    if "response" not in columns:
        conn.execute("ALTER TABLE prompts ADD COLUMN response TEXT")
    conn.commit()
    return conn


def fetch_context(conn, limit):
    if limit is None:
        cur = conn.execute("SELECT id, body, created_at, response FROM prompts ORDER BY id")
        return cur.fetchall()
    cur = conn.execute(
        "SELECT id, body, created_at, response FROM prompts ORDER BY id DESC LIMIT ?", (limit,)
    )
    return list(reversed(cur.fetchall()))


def store(conn, body, response=None):
    conn.execute(
        "INSERT INTO prompts (body, created_at, response) VALUES (?, ?, ?)",
        (body, datetime.now(timezone.utc).isoformat(timespec="seconds"), response),
    )
    conn.commit()


def print_rows(rows, header):
    print(f"\n{header}:")
    if not rows:
        print("  (empty)")
    for row_id, body, created_at, _response in rows:
        print(f"  [{row_id}] {created_at}  {body}")


def coder_response(body, rows, backend):
    """Planner and Tester bypassed: the prompt and past interactions go straight to the Coder Agent."""
    from agents.coder_agent import CoderAgent, Interaction, plan_from_request

    context = [Interaction(prompt, response) for _id, prompt, _created, response in rows]
    output = CoderAgent(backend=backend).generate_solution(plan_from_request(body, context))
    changed = "\n".join(f"  {path}" for path in output.files) or "  (none)"
    return f"{output.summary}\n\nfiles changed:\n{changed}"


def handle(conn, body, limit, backend, agent):
    rows = fetch_context(conn, limit)
    print_rows(rows, "context")
    try:
        if agent == "coder":
            response = coder_response(body, rows, backend)
        else:
            response = claude_response(body, backend)
    except Exception as exc:
        print(f"\nerror: {exc}\n", file=sys.stderr)
        store(conn, body)
        return
    print(f"\n{response}\n")
    store(conn, body, response)


def repl(conn, limit, backend, agent):
    print("Type a prompt and press enter. Ctrl-D or exit to quit.")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            print()
            return
        if line in {"exit", "quit"}:
            return
        if not line:
            continue
        handle(conn, line, limit, backend, agent)


def main():
    parser = argparse.ArgumentParser(
        description="Store prompts in SQLite and print the previous ones as context."
    )
    parser.add_argument("prompt", nargs="*", help="prompt text; omit for interactive mode")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite path (default: {DEFAULT_DB})")
    parser.add_argument(
        "-n", "--limit", type=int, default=10, help="how many prior prompts to show (default: 10)"
    )
    parser.add_argument(
        "--backend",
        choices=BACKENDS,
        default=DEFAULT_BACKEND,
        help="api: Claude API with ANTHROPIC_API_KEY; subscription: Claude Code CLI "
        f"with your Claude login (default: {DEFAULT_BACKEND})",
    )
    parser.add_argument(
        "--agent",
        choices=AGENTS,
        default=DEFAULT_AGENT,
        help="coder: Coder Agent with file tools, planner and tester bypassed; "
        f"ack: acknowledge the prompt only (default: {DEFAULT_AGENT})",
    )
    parser.add_argument("--history", action="store_true", help="print every stored prompt and exit")
    parser.add_argument("--reset", action="store_true", help="delete all stored prompts and exit")
    args = parser.parse_args()
    if args.backend not in BACKENDS:
        parser.error(f"CLAUDE_BACKEND must be one of {', '.join(BACKENDS)}, got {args.backend!r}")
    if args.agent not in AGENTS:
        parser.error(f"TRINITY_AGENT must be one of {', '.join(AGENTS)}, got {args.agent!r}")

    conn = connect(args.db)
    try:
        run(conn, args)
    finally:
        conn.close()


def run(conn, args):
    if args.reset:
        conn.execute("DELETE FROM prompts")
        conn.commit()
        print(f"Cleared all prompts from {args.db}")
        return

    if args.history:
        print_rows(fetch_context(conn, None), "history")
        return

    if args.prompt:
        handle(conn, " ".join(args.prompt), args.limit, args.backend, args.agent)
    elif sys.stdin.isatty():
        repl(conn, args.limit, args.backend, args.agent)
    else:
        for line in sys.stdin:
            line = line.strip()
            if line:
                handle(conn, line, args.limit, args.backend, args.agent)


if __name__ == "__main__":
    main()

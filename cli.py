import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone

DEFAULT_DB = os.environ.get("CONTEXT_DB", "/data/context.db")
RESPONSE = "Response here according to prompt and context."


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
    conn.commit()
    return conn


def fetch_context(conn, limit):
    if limit is None:
        cur = conn.execute("SELECT id, body, created_at FROM prompts ORDER BY id")
        return cur.fetchall()
    cur = conn.execute(
        "SELECT id, body, created_at FROM prompts ORDER BY id DESC LIMIT ?", (limit,)
    )
    return list(reversed(cur.fetchall()))


def store(conn, body):
    conn.execute(
        "INSERT INTO prompts (body, created_at) VALUES (?, ?)",
        (body, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    conn.commit()


def print_rows(rows, header):
    print(f"\n{header}:")
    if not rows:
        print("  (empty)")
    for row_id, body, created_at in rows:
        print(f"  [{row_id}] {created_at}  {body}")


def handle(conn, body, limit):
    print_rows(fetch_context(conn, limit), "context")
    print(f"\n{RESPONSE}\n")
    store(conn, body)


def repl(conn, limit):
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
        handle(conn, line, limit)


def main():
    parser = argparse.ArgumentParser(
        description="Store prompts in SQLite and print the previous ones as context."
    )
    parser.add_argument("prompt", nargs="*", help="prompt text; omit for interactive mode")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite path (default: {DEFAULT_DB})")
    parser.add_argument(
        "-n", "--limit", type=int, default=10, help="how many prior prompts to show (default: 10)"
    )
    parser.add_argument("--history", action="store_true", help="print every stored prompt and exit")
    parser.add_argument("--reset", action="store_true", help="delete all stored prompts and exit")
    args = parser.parse_args()

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
        handle(conn, " ".join(args.prompt), args.limit)
    elif sys.stdin.isatty():
        repl(conn, args.limit)
    else:
        for line in sys.stdin:
            line = line.strip()
            if line:
                handle(conn, line, args.limit)


if __name__ == "__main__":
    main()

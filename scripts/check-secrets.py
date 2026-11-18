#!/usr/bin/env python3
"""Fail if a tracked file looks like it contains a real secret (Report 6 hardening).

Run from the repo root: `python3 scripts/check-secrets.py`. CI runs it on every PR.
Standard library only. It checks files git tracks, so ignored files (.env) are out of scope
on purpose; it also fails if a .env file is tracked at all.

Known, intentional values are allowed: the dev-only defaults in apps/api/app/config.py
(production refuses to start with them) and the demo password printed by the seed.
"""

import re
import subprocess
import sys
from pathlib import Path

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe live key", re.compile(r"\b[sr]k_live_[A-Za-z0-9]{16,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    (
        "secret assigned in an env file",
        re.compile(
            r"^\s*(?:JWT_SECRET|TICKET_SIGNING_SECRET|SMTP_PASSWORD|SECRET_KEY)\s*=\s*(\S{8,})",
            re.MULTILINE,
        ),
    ),
]
ALLOWED_VALUES = {
    "dev-only-insecure-jwt-secret-change-me",
    "dev-only-insecure-ticket-secret-change-me",
}
SKIP_SUFFIXES = {".png", ".jpg", ".ico", ".pdf", ".ttf", ".woff", ".woff2", ".lock"}
SKIP_NAMES = {"package-lock.json", "uv.lock", "skills-lock.json"}


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    return [Path(p) for p in out.decode().split("\0") if p]


def main() -> int:
    problems: list[str] = []
    for path in tracked_files():
        if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
            problems.append(f"{path}: an environment file is tracked; remove it and keep it local")
            continue
        if path.suffix in SKIP_SUFFIXES or path.name in SKIP_NAMES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(1) if match.groups() else match.group(0)
                if value.strip("'\"") in ALLOWED_VALUES:
                    continue
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{path}:{line}: looks like a {label}")
    for problem in problems:
        print(problem)
    if problems:
        print(f"\n{len(problems)} possible secret(s). Move them to .env (never committed).")
        return 1
    print(f"No secrets found in {len(tracked_files())} tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

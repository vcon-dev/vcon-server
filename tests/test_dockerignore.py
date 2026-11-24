"""The images run `COPY . /app`, so anything .dockerignore lets through is baked into a layer.

A build from a checkout that holds a `.env` (service tokens and keys) or backup copies of the rendered
config puts those secrets into the image. Matching follows Docker's rules for
.dockerignore: patterns are relative to the context root, `*` stops at `/`, `**` crosses it, a
pattern that matches a directory covers everything under it, and `!` re-includes.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _regex(pattern):
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def _excluded(path, patterns):
    parts = path.split("/")
    prefixes = ["/".join(parts[: n + 1]) for n in range(len(parts))]
    excluded = False
    for raw in patterns:
        negate = raw.startswith("!")
        regex = _regex(raw[1:] if negate else raw)
        if any(regex.match(p) for p in prefixes):
            excluded = not negate
    return excluded


def _patterns():
    lines = (ROOT / ".dockerignore").read_text().splitlines()
    return [ln.strip().lstrip("/") for ln in lines if ln.strip() and not ln.startswith("#")]


SECRET_PATHS = [
    ".env",
    "config.yml",
    "config.yml.bak-example",
    "docker-compose.override.yml.bak-example",
    "conserver/links/example/__init__.py.bak-example",
]
BUILD_PATHS = ["pyproject.toml", "uv.lock", "conserver/main.py", "common/lib/redaction.py", "docker/wait_for_redis.sh"]


def test_secret_bearing_files_stay_out_of_the_build_context():
    leaked = [p for p in SECRET_PATHS if not _excluded(p, _patterns())]
    assert leaked == []


def test_files_the_build_needs_stay_in():
    dropped = [p for p in BUILD_PATHS if _excluded(p, _patterns())]
    assert dropped == []

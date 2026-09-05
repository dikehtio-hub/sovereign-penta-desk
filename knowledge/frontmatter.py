"""OKF v0.2 frontmatter: parse, validate, serialize, with the DEV ``dev:`` namespace.

THE CONTRACT (WIKI_SCHEMA.md section 3). A page is a YAML block between two
``---`` lines followed by a Markdown body. OKF v0.2 requires exactly one
field, ``type``. Recommended: ``title``, ``description``, ``tags``,
``resource``. Optional families: ``generated {by, at}``, ``verified`` (a
mapping or a list of ``{by, at}``), ``status draft|stable|deprecated``,
``stale_after`` (ISO 8601), ``sources`` (a list; each entry REQUIRES
``resource``). Actor strings follow the OKF convention: ``human:<id>``,
``process:<id>`` or ``<producer>/<version>``.

THE DEV NAMESPACE. Everything DEV adds sits under ``dev:`` so any OKF
consumer (which MUST NOT reject unknown keys) still reads the page.
``dev.asserts`` is a list of ``{file, pattern, claim}``: the page claims
something about a source file and names the file and a regex that must
still match, so lint C1 can catch copied-state drift. ``dev.parameters`` is
a list of ``{name, value, file, pattern}``: the page states a number, and
the regex's first group must still equal it in the owning file.
``dev.window {start, end}`` marks a registration window during which the
page may not be edited (lint C5, and ``pages.write_page`` refuses).

Nothing here touches the filesystem; ``pages.py`` does the I/O.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import yaml

STATUSES = ("draft", "stable", "deprecated")

ACTOR_RE = re.compile(
    r"^(?:human:[A-Za-z0-9_.\-]+|process:[A-Za-z0-9_.\-/]+|[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)$"
)

# Recommended OKF keys that must be strings when present.
_STRING_KEYS = ("type", "title", "description", "resource")


class FrontmatterError(ValueError):
    """Raised when a document has no parseable frontmatter block."""


def _normalise_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split(text: str) -> tuple[str | None, str]:
    """Return (yaml_text or None, body). None means no frontmatter block."""
    text = _normalise_newlines(text)
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    while end != -1:
        after = text[end + 4 : end + 5]
        if after in ("", "\n"):
            break
        end = text.find("\n---", end + 4)
    if end == -1:
        return None, text
    yaml_text = text[4:end]
    body = text[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    return yaml_text, body


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Parse a page. Raises FrontmatterError when the block is missing or malformed."""
    yaml_text, body = split(text)
    if yaml_text is None:
        raise FrontmatterError("no frontmatter block (file must start with '---')")
    try:
        meta = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:  # pragma: no cover - message text varies by version
        raise FrontmatterError(f"frontmatter is not valid YAML: {exc}") from exc
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return meta, body


def try_parse(text: str) -> tuple[dict[str, Any] | None, str, str | None]:
    """Non-raising parse: (meta or None, body, error message or None)."""
    try:
        meta, body = parse(text)
        return meta, body, None
    except FrontmatterError as exc:
        return None, text, str(exc)


def serialize(meta: dict[str, Any], body: str) -> str:
    """Render a page. Key order is preserved (sort_keys=False) so `type` leads."""
    dumped = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, default_flow_style=False)
    body = _normalise_newlines(body)
    if body and not body.endswith("\n"):
        body += "\n"
    return f"---\n{dumped}---\n{body}"


def parse_iso8601(value: Any) -> datetime:
    """Parse an ISO 8601 instant into an aware UTC datetime. Raises ValueError."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    else:
        raise ValueError(f"not an ISO 8601 string: {value!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_actor(value: Any) -> bool:
    return isinstance(value, str) and bool(ACTOR_RE.match(value))


def _check_actor_at(obj: Any, where: str, issues: list[str], require_by: bool = True) -> None:
    if not isinstance(obj, dict):
        issues.append(f"{where} must be a mapping with `by` and optional `at`")
        return
    by = obj.get("by")
    if by is None:
        if require_by:
            issues.append(f"{where}.by is required")
    elif not is_actor(by):
        issues.append(f"{where}.by {by!r} is not an actor (human:<id> | process:<id> | <producer>/<version>)")
    if "at" in obj:
        try:
            parse_iso8601(obj["at"])
        except ValueError:
            issues.append(f"{where}.at {obj['at']!r} is not ISO 8601")


def validate(meta: dict[str, Any]) -> list[str]:
    """Return a list of issues. Empty list means OKF v0.2 + dev: conformant."""
    issues: list[str] = []
    if not isinstance(meta, dict):
        return ["frontmatter must be a mapping"]

    t = meta.get("type")
    if not isinstance(t, str) or not t.strip():
        issues.append("`type` is required and must be a non-empty string (OKF v0.2)")

    for key in _STRING_KEYS:
        if key in meta and key != "type" and not isinstance(meta[key], str):
            issues.append(f"`{key}` must be a string")

    if "tags" in meta:
        tags = meta["tags"]
        if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
            issues.append("`tags` must be a list of strings")

    if "generated" in meta:
        _check_actor_at(meta["generated"], "generated", issues)

    if "verified" in meta:
        v = meta["verified"]
        entries = v if isinstance(v, list) else [v]
        for i, entry in enumerate(entries):
            _check_actor_at(entry, f"verified[{i}]", issues)

    if "status" in meta and meta["status"] not in STATUSES:
        issues.append(f"`status` must be one of {'|'.join(STATUSES)}, got {meta['status']!r}")

    if "stale_after" in meta:
        try:
            parse_iso8601(meta["stale_after"])
        except ValueError:
            issues.append(f"`stale_after` {meta['stale_after']!r} is not ISO 8601")

    if "sources" in meta:
        srcs = meta["sources"]
        if not isinstance(srcs, list):
            issues.append("`sources` must be a list")
        else:
            for i, s in enumerate(srcs):
                if not isinstance(s, dict):
                    issues.append(f"sources[{i}] must be a mapping")
                    continue
                if not isinstance(s.get("resource"), str) or not s["resource"].strip():
                    issues.append(f"sources[{i}].resource is required (OKF v0.2)")
                if "author" in s and not is_actor(s["author"]):
                    issues.append(f"sources[{i}].author {s['author']!r} is not an actor")
                if "last_modified" in s:
                    try:
                        parse_iso8601(s["last_modified"])
                    except ValueError:
                        issues.append(f"sources[{i}].last_modified is not ISO 8601")

    if "dev" in meta:
        issues.extend(_validate_dev(meta["dev"]))
    return issues


def _validate_dev(dev: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(dev, dict):
        return ["`dev` must be a mapping"]
    if "asserts" in dev:
        if not isinstance(dev["asserts"], list):
            issues.append("dev.asserts must be a list")
        else:
            for i, a in enumerate(dev["asserts"]):
                if not isinstance(a, dict) or not isinstance(a.get("file"), str) or not isinstance(a.get("pattern"), str):
                    issues.append(f"dev.asserts[{i}] needs string `file` and `pattern`")
                    continue
                try:
                    re.compile(a["pattern"])
                except re.error as exc:
                    issues.append(f"dev.asserts[{i}].pattern is not a valid regex: {exc}")
    if "parameters" in dev:
        if not isinstance(dev["parameters"], list):
            issues.append("dev.parameters must be a list")
        else:
            for i, p in enumerate(dev["parameters"]):
                if not isinstance(p, dict) or not isinstance(p.get("name"), str) or "value" not in p \
                        or not isinstance(p.get("file"), str) \
                        or not (isinstance(p.get("pattern"), str) or isinstance(p.get("json_path"), str)):
                    issues.append(f"dev.parameters[{i}] needs `name`, `value`, string `file` and `pattern` or `json_path`")
                    continue
                if isinstance(p.get("pattern"), str):
                    try:
                        re.compile(p["pattern"])
                    except re.error as exc:
                        issues.append(f"dev.parameters[{i}].pattern is not a valid regex: {exc}")
    if "window" in dev:
        w = dev["window"]
        if not isinstance(w, dict) or "start" not in w or "end" not in w:
            issues.append("dev.window needs `start` and `end`")
        else:
            try:
                start, end = parse_iso8601(w["start"]), parse_iso8601(w["end"])
                if end <= start:
                    issues.append("dev.window.end must be after dev.window.start")
            except ValueError:
                issues.append("dev.window start/end must be ISO 8601")
    for key in ("desk", "item", "round"):
        if key in dev and not isinstance(dev[key], int):
            issues.append(f"dev.{key} must be an integer")
    for key in ("requires_files", "tokens"):
        if key in dev:
            v = dev[key]
            if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
                issues.append(f"dev.{key} must be a list of non-empty strings")
    if "token_id" in dev and not isinstance(dev["token_id"], str):
        issues.append("dev.token_id must be a string")
    if "history" in dev and (not isinstance(dev["history"], list) or not all(isinstance(x, dict) for x in dev["history"])):
        issues.append("dev.history must be a list of mappings")
    return issues

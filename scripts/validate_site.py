#!/usr/bin/env python3
"""Validate local links, duplicate IDs, and required research-site controls."""

from __future__ import annotations

import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []
        self.buttons = 0
        self.details = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        if tag == "a" and values.get("href"):
            self.links.append(str(values["href"]))
        if tag == "button":
            self.buttons += 1
        if tag == "details":
            self.details += 1


def validate_page(path: Path) -> list[str]:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    errors = []
    duplicates = sorted({value for value in parser.ids if parser.ids.count(value) > 1})
    if duplicates:
        errors.append(f"{path.relative_to(REPO_ROOT)}: duplicate IDs: {', '.join(duplicates)}")
    for link in parser.links:
        parsed = urllib.parse.urlparse(link)
        if parsed.scheme or parsed.netloc or link.startswith(("#", "mailto:")):
            continue
        target = (path.parent / urllib.parse.unquote(parsed.path)).resolve()
        if not target.is_relative_to(REPO_ROOT.resolve()):
            errors.append(f"{path.relative_to(REPO_ROOT)}: link escapes repository: {link}")
        elif not target.exists():
            errors.append(f"{path.relative_to(REPO_ROOT)}: missing local link target: {link}")
    if path.name in {"index.html", "assistant-benchmark.html", "methodology.html", "research-runs.html"} and not parser.buttons:
        errors.append(f"{path.name}: mobile menu button is missing")
    if path.name == "research-runs.html" and not parser.details:
        errors.append("research-runs.html: collapsed model selector is missing")
    return errors


def main() -> int:
    pages = [
        REPO_ROOT / "index.html", REPO_ROOT / "assistant-benchmark.html",
        REPO_ROOT / "methodology.html", REPO_ROOT / "research-runs.html",
        *sorted((REPO_ROOT / "run-pages").glob("*.html")),
    ]
    errors = [error for page in pages for error in validate_page(page)]
    if errors:
        print("Site validation failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(f"VALID: {len(pages)} static pages and their local links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

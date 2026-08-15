"""Publish one validated suite from an isolated clone of the research repository."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import Settings
from .repository import Repository


def _run(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True)
    return completed.stdout.strip()


def _copy_suite(source_root: Path, clone: Path, artifact: dict[str, Any]) -> None:
    published = artifact.get("published") or {}
    if "published_csv" in published:
        relative = Path(str(published["published_csv"]))
        target = clone / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative, target)
        return
    if "published_case_study" in published:
        relative = Path(str(published["published_case_study"]))
        target = clone / relative
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_root / relative, target)
        return
    raise RuntimeError("Research result contains no publishable assistant row or editorial case study")


def publish_one(settings: Settings, publication: dict[str, Any]) -> str:
    if not settings.auto_publish_main:
        raise RuntimeError("AUTO_PUBLISH_MAIN is disabled")
    origin = settings.publish_repository_url
    if not origin:
        origin = _run(
            ["git", "config", "--get", f"remote.{settings.publish_remote}.url"],
            settings.research_root,
        )
    with tempfile.TemporaryDirectory(prefix="research-publisher-") as temporary:
        clone = Path(temporary) / "research"
        _run(["git", "clone", "--depth", "1", "--branch", settings.publish_branch, origin, str(clone)], settings.research_root)
        # The clone has no repository-specific identity. Deliberately inherit
        # the configured developer identity, rather than inventing a bot one.
        author_name = _run(["git", "config", "--get", "user.name"], clone)
        author_email = _run(["git", "config", "--get", "user.email"], clone)
        _run(["git", "config", "user.name", author_name], clone)
        _run(["git", "config", "user.email", author_email], clone)
        _copy_suite(settings.research_root, clone, dict(publication["artifact"]))
        _run(["python", "scripts/build_radar.py"], clone)
        _run(
            [
                "git", "add", "docs/model-comparisons", "docs/assistant-benchmark",
                "index.html", "methodology.html", "assistant-benchmark.html",
                "model-comparison.json", "model-comparison-radar.svg",
                "assistant-model-results.csv", "assistant-benchmark.json",
                "assistant-benchmark-score.svg", "assistant-benchmark-speed-quality.svg",
                "assistant-benchmark-latency.svg", "assistant-benchmark-categories.svg",
            ],
            clone,
        )
        if _run(["git", "status", "--porcelain"], clone) == "":
            return _run(["git", "rev-parse", "HEAD"], clone)
        subject = f"data(local): publish {publication['cohort']} suite {publication['research_job_id'][:8]}"
        _run(["git", "commit", "-m", subject], clone)
        for attempt in range(2):
            try:
                _run(["git", "push", settings.publish_remote, f"HEAD:{settings.publish_branch}"], clone)
                return _run(["git", "rev-parse", "HEAD"], clone)
            except subprocess.CalledProcessError:
                if attempt:
                    raise
                _run(["git", "fetch", settings.publish_remote, settings.publish_branch], clone)
                _run(["git", "rebase", f"{settings.publish_remote}/{settings.publish_branch}"], clone)
    raise RuntimeError("Publisher exhausted its push retry")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    settings = Settings.from_env()
    repository = Repository(settings.database_dsn)
    while True:
        # Leave publication work queued if direct publishing is intentionally
        # disabled; turning it back on resumes without re-running inference.
        if not settings.auto_publish_main:
            if args.once:
                return 0
            time.sleep(args.poll_seconds)
            continue
        publication = repository.claim_publication("publisher")
        if publication is None:
            if args.once:
                return 0
            time.sleep(args.poll_seconds)
            continue
        try:
            commit = publish_one(settings, publication)
            repository.finish_publication(str(publication["id"]), commit_sha=commit)
        except Exception as exc:
            repository.fail_publication(str(publication["id"]), f"{type(exc).__name__}: {exc}")
        if args.once:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())

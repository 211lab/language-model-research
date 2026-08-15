from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .application import BudgetExceeded, ContentScorer, discover_case_studies, load_rubric, write_aggregate
from .infrastructure import OpenRouterEvaluator, Telemetry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score SteadyBurn case-study content.")
    parser.add_argument("--root", type=Path, default=Path("docs/model-comparisons"))
    parser.add_argument("--case-study", type=Path, action="append")
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--aggregate-existing", action="store_true", help="Rebuild the aggregate report from existing CONTENT_SCORE.json files without calling an evaluator.")
    parser.add_argument("--max-cost", type=float, default=5.0)
    parser.add_argument("--log-level", choices=("INFO", "DEBUG"), default="INFO")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    telemetry = Telemetry(root / "scoring-runs" / "telemetry.jsonl", verbose=args.log_level == "DEBUG")
    if args.aggregate_existing:
        reports = []
        for score_path in sorted(root.rglob("CONTENT_SCORE.json")):
            try:
                reports.append(json.loads(score_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        if not reports:
            raise SystemExit("No existing CONTENT_SCORE.json reports found.")
        write_aggregate(root, reports, "aggregate-existing", 0.0)
        print(f"Aggregated {len(reports)} existing case studies; evaluator cost $0.000000")
        return 0
    rubric = load_rubric(Path(__file__).parent / "rubrics" / "steadyburn-v1.json")
    requested = [path.resolve() for path in args.case_study] if args.case_study else None
    studies = discover_case_studies(root, requested)
    if not studies:
        raise SystemExit("No complete case studies found.")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not args.dry_run and not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required unless --dry-run is used.")
    evaluator = None if args.dry_run else OpenRouterEvaluator(api_key, telemetry)
    scorer = ContentScorer(root, rubric, evaluator, telemetry, args.max_cost, args.resume, args.force)
    telemetry.emit("run_started", run_id=scorer.run_id, case_studies=len(studies), max_cost=args.max_cost, dry_run=args.dry_run)
    reports = []
    failures = []
    for study in studies:
        try:
            reports.append(scorer.score_study(study))
        except BudgetExceeded as exc:
            telemetry.emit("run_failed", run_id=scorer.run_id, reason=str(exc), cost=round(scorer.spent, 6))
            write_aggregate(root, reports, scorer.run_id, scorer.spent)
            return 2
        except Exception as exc:
            failures.append({"case_study": study.identifier, "reason": type(exc).__name__})
            telemetry.emit("case_study_failed", run_id=scorer.run_id, case_study=study.identifier, reason=type(exc).__name__)
    if failures:
        telemetry.emit("run_completed_with_failures", run_id=scorer.run_id, failures=failures, cost=round(scorer.spent, 6))
    else:
        telemetry.emit("run_completed", run_id=scorer.run_id, case_studies=len(reports), cost=round(scorer.spent, 6))
    write_aggregate(root, reports, scorer.run_id, scorer.spent)
    if failures:
        return 1
    print(f"Scored {len(reports)} case studies; evaluator cost {chr(36)}{scorer.spent:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

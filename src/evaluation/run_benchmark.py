import os
import sys
import json
import argparse
from typing import Optional

from evaluation.runner import EvaluationRunner
from evaluation.report import (
    generate_evaluation_report,
    report_to_json,
    generate_markdown_report,
    print_evaluation_summary,
    compare_benchmark_reports
)


def run_benchmark(
    output_dir: str = "evaluation_results",
    baseline_path: Optional[str] = None,
    tolerance: float = 0.05
) -> int:
    """
    Execute the automated benchmark across all 8 synthetic cases,
    writing benchmark_report.json and benchmark_report.md to output_dir.
    """
    runner = EvaluationRunner()
    results = runner.run_all()
    report = generate_evaluation_report(results)

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "benchmark_report.json")
    md_path = os.path.join(output_dir, "benchmark_report.md")

    # Generate and save JSON report
    json_content = report_to_json(report, run_id="benchmark_run_deterministic")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json_content)

    # Generate and save Markdown report
    md_content = generate_markdown_report(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Print clean stdout summary
    print(print_evaluation_summary(report))

    # Optional regression comparison
    if baseline_path and os.path.exists(baseline_path):
        try:
            with open(baseline_path, "r", encoding="utf-8") as f:
                baseline_data = json.load(f)
            current_data = json.loads(json_content)
            comp = compare_benchmark_reports(current_data, baseline_data, tolerance=tolerance)
            if comp["has_regressions"]:
                print("\n[WARNING] Metric Regressions Detected:")
                for reg in comp["regressions"]:
                    print(f"  - {reg}")
            else:
                print("\n[OK] No metric regressions detected against baseline.")
        except Exception as e:
            print(f"\n[WARNING] Error comparing against baseline: {e}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Run Mechanical Engineering Drawing Intelligence Benchmark"
    )
    parser.add_argument(
        "--output-dir",
        default="evaluation_results",
        help="Directory to save benchmark reports (default: evaluation_results)"
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Path to previous benchmark_report.json for regression checking"
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.05,
        help="Allowed drop before flagging regression (default: 0.05)"
    )
    args = parser.parse_args()

    sys.exit(run_benchmark(
        output_dir=args.output_dir,
        baseline_path=args.baseline,
        tolerance=args.tolerance
    ))


if __name__ == "__main__":
    main()

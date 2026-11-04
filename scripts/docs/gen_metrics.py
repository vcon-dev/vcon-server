#!/usr/bin/env python3
"""Generate docs/reference/metrics.md from calls to the lib.metrics helpers."""

import ast
import sys
from collections import defaultdict

from _docslib import (
    call_name,
    check_stale,
    code,
    constant,
    description,
    iter_python_files,
    keyword,
    load_section,
    parse,
    rel,
    table,
    write_page,
)

HELPERS = {
    "increment_counter": "counter",
    "add_updown_counter": "up-down counter",
    "record_histogram": "histogram",
    "register_observable_gauge": "observable gauge",
}
# The helpers themselves take the name as a parameter.
SKIP = {"common/lib/metrics.py"}


def collect():
    metrics = defaultdict(lambda: {"types": set(), "files": set()})
    dynamic = set()
    for path in iter_python_files():
        name = rel(path)
        if name in SKIP:
            continue
        for node in ast.walk(parse(path)):
            if not (isinstance(node, ast.Call) and call_name(node) in HELPERS):
                continue
            argument = node.args[0] if node.args else keyword(node, "metric_name")
            metric = constant(argument)
            if isinstance(metric, str):
                metrics[metric]["types"].add(HELPERS[call_name(node)])
                metrics[metric]["files"].add(name)
            else:
                dynamic.add((name, ast.unparse(argument)))
    return metrics, dynamic


def main():
    block = load_section("metrics")
    metrics, dynamic = collect()
    check_stale("metrics", block, metrics)

    rows = [
        [
            code(metric),
            ", ".join(sorted(metrics[metric]["types"])),
            "<br>".join(code(f) for f in sorted(metrics[metric]["files"])),
            description(block, metric),
        ]
        for metric in sorted(metrics)
    ]
    sections = [
        f"The code emits {len(rows)} metric names.",
        table(["Metric", "Type", "Emitted in", "Description"], rows),
    ]
    if dynamic:
        print(f"warning: {len(dynamic)} dynamic metric names", file=sys.stderr)
        sections += [
            "## Dynamic metric names",
            "These calls compute the name at run time, so the table cannot list them.",
            table(
                ["File", "Expression"],
                [[code(f), code(expr)] for f, expr in sorted(dynamic)],
            ),
        ]
    write_page("metrics.md", "Metrics", "gen_metrics.py", block, sections)


if __name__ == "__main__":
    main()

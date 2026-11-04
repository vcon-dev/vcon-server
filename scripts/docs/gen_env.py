#!/usr/bin/env python3
"""Generate docs/reference/environment.md from environment reads in the code.

Covers common/settings.py and every direct os.getenv, os.environ.get,
os.environ[...] and "X" in os.environ read under api, common and conserver.
"""

import ast
import sys
from collections import defaultdict

from _docslib import (
    call_name,
    check_stale,
    code,
    constant,
    description,
    entry,
    iter_python_files,
    load_section,
    parse,
    rel,
    table,
    write_page,
)

NO_DEFAULT = "none"
REQUIRED = "required"


def is_environ(node):
    if isinstance(node, ast.Attribute):
        return node.attr == "environ"
    return isinstance(node, ast.Name) and node.id == "environ"


def is_env_call(node):
    """True for os.getenv(...), getenv(...) and os.environ.get(...)."""
    if not isinstance(node, ast.Call) or not node.args:
        return False
    if call_name(node) == "getenv":
        return True
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and is_environ(node.func.value)
    )


def default_text(call):
    if len(call.args) < 2:
        return NO_DEFAULT
    node = call.args[1]
    if isinstance(node, ast.Constant):
        if node.value is None:
            return NO_DEFAULT
        return code(node.value) if node.value != "" else code('""')
    return code(ast.unparse(node))


def value_type(node):
    """Work out how the surrounding statement treats the value."""
    child, parent = node, getattr(node, "parent", None)
    while parent is not None and not isinstance(parent, ast.stmt):
        if isinstance(parent, ast.Call) and call_name(parent) in ("int", "float"):
            return "integer" if call_name(parent) == "int" else "float"
        if (
            isinstance(parent, ast.Compare)
            and parent.left is child
            and isinstance(parent.ops[0], ast.In)
        ):
            return "boolean"
        child, parent = parent, getattr(parent, "parent", None)
    return "string"


def collect():
    reads = defaultdict(list)  # variable -> [(file, default, type)]
    dynamic = set()
    for path in iter_python_files():
        name = rel(path)
        for node in ast.walk(parse(path)):
            if is_env_call(node):
                variable = constant(node.args[0])
                if isinstance(variable, str):
                    reads[variable].append((name, default_text(node), value_type(node)))
                else:
                    dynamic.add((name, ast.unparse(node)))
            elif (
                isinstance(node, ast.Subscript)
                and is_environ(node.value)
                and isinstance(node.ctx, ast.Load)
            ):
                variable = constant(node.slice)
                if isinstance(variable, str):
                    reads[variable].append((name, REQUIRED, "string"))
                else:
                    dynamic.add((name, ast.unparse(node)))
            elif (
                isinstance(node, ast.Compare)
                and isinstance(node.ops[0], ast.In)
                and is_environ(node.comparators[0])
            ):
                variable = constant(node.left)
                if isinstance(variable, str):
                    reads[variable].append((name, NO_DEFAULT, "string"))
                else:
                    dynamic.add((name, ast.unparse(node)))
    return reads, dynamic


def render_default(sites):
    by_value = defaultdict(set)
    for name, default, _ in sites:
        by_value[default].add(name)
    if len(by_value) == 1:
        return next(iter(by_value))
    return "<br>".join(
        f"{value} in " + ", ".join(code(f) for f in sorted(files))
        for value, files in sorted(by_value.items())
    )


def main():
    block = load_section("environment")
    reads, dynamic = collect()
    check_stale("environment", block, reads)

    rows = []
    for variable in sorted(reads):
        sites = reads[variable]
        rows.append(
            [
                code(variable),
                entry(block, variable).get("default") or render_default(sites),
                ", ".join(sorted({site[2] for site in sites})),
                "<br>".join(code(f) for f in sorted({site[0] for site in sites})),
                description(block, variable),
            ]
        )

    sections = [
        f"The code reads {len(rows)} variables.",
        table(["Variable", "Default", "Type", "Read in", "Description"], rows),
    ]
    if dynamic:
        print(f"warning: {len(dynamic)} dynamic environment reads", file=sys.stderr)
        sections += [
            "## Dynamic reads",
            "These reads compute the variable name at run time, so the table cannot list them.",
            table(
                ["File", "Expression"],
                [[code(f), code(expr)] for f, expr in sorted(dynamic)],
            ),
        ]
    write_page("environment.md", "Environment variables", "gen_env.py", block, sections)


if __name__ == "__main__":
    main()

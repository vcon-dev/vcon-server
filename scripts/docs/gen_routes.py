#!/usr/bin/env python3
"""Generate docs/reference/api-routes.md from the decorators in api/api.py."""

import ast

from _docslib import (
    REPO,
    call_name,
    check_stale,
    code,
    constant,
    description,
    keyword,
    load_section,
    parse,
    table,
    write_page,
)

METHODS = {"get", "post", "put", "patch", "delete"}
AUTH_NONE = "none"
AUTH_DEPENDENCIES = {"get_api_key": "API key"}
AUTH_BODY_CALLS = {"validate_ingress_api_key": "ingress API key"}


def router_auth(tree):
    """Map each router name to its auth label and prefix from include_router."""
    routers = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and call_name(node) == "include_router"):
            continue
        router = node.args[0].id
        label = AUTH_NONE
        dependencies = keyword(node, "dependencies")
        if dependencies is not None:
            for dependency in ast.walk(dependencies):
                if isinstance(dependency, ast.Name) and dependency.id in AUTH_DEPENDENCIES:
                    label = AUTH_DEPENDENCIES[dependency.id]
        routers[router] = (label, constant(keyword(node, "prefix")) or "")
    return routers


def body_auth(function):
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and call_name(node) in AUTH_BODY_CALLS:
            return AUTH_BODY_CALLS[call_name(node)]
    return None


def collect(tree):
    routers = router_auth(tree)
    routes = []
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in function.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in METHODS
                and isinstance(decorator.func.value, ast.Name)
            ):
                continue
            owner = decorator.func.value.id
            if owner != "app" and owner not in routers:
                continue
            auth, prefix = routers.get(owner, (AUTH_NONE, ""))
            tags = keyword(decorator, "tags")
            routes.append(
                {
                    "method": decorator.func.attr.upper(),
                    "path": prefix + constant(decorator.args[0]),
                    "auth": body_auth(function) or auth,
                    "status": constant(keyword(decorator, "status_code")) or 200,
                    "summary": constant(keyword(decorator, "summary")) or "",
                    "tags": [t.value for t in tags.elts] if tags is not None else [],
                }
            )
    return sorted(routes, key=lambda r: (r["path"], r["method"]))


def main():
    block = load_section("routes")
    routes = collect(parse(REPO / "api" / "api.py"))
    keys = [f"{r['method']} {r['path']}" for r in routes]
    check_stale("routes", block, keys)

    rows = [
        [
            r["method"],
            code(r["path"]),
            r["auth"],
            r["status"],
            ", ".join(r["tags"]),
            r["summary"],
            description(block, key, required=False),
        ]
        for r, key in zip(routes, keys)
    ]
    sections = [
        f"`api/api.py` defines {len(rows)} routes.",
        table(["Method", "Path", "Auth", "Success status", "Tag", "Summary", "Notes"], rows),
    ]
    write_page("api-routes.md", "API routes", "gen_routes.py", block, sections)


if __name__ == "__main__":
    main()

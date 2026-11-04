#!/usr/bin/env python3
"""Generate docs/reference/ports.md from docker-compose.yml."""

import re

import yaml

from _docslib import (
    REPO,
    check_stale,
    code,
    description,
    load_section,
    table,
    write_page,
)

VARIABLE = re.compile(r"^\$\{(?P<name>\w+)(?::?-(?P<default>[^}]*))?\}$")


def split_short_form(text):
    """Split a short port mapping, keeping a ${VAR:-default} host part whole."""
    text, _, protocol = str(text).partition("/")
    parts = re.findall(r"\$\{[^}]*\}|[^:]+", text)
    if len(parts) == 1:
        return "", parts[0], protocol or "tcp"
    return parts[-2], parts[-1], protocol or "tcp"


def parse_port(spec):
    """Return (host, host variable, container, protocol)."""
    if isinstance(spec, dict):
        host = str(spec.get("published", ""))
        container = str(spec["target"])
        protocol = spec.get("protocol", "tcp")
    else:
        host, container, protocol = split_short_form(spec)
    variable = ""
    match = VARIABLE.match(host)
    if match:
        variable = match["name"]
        host = match["default"] or ""
    return host, variable, container, protocol


def image_label(service):
    if "image" in service:
        return code(service["image"].split("@")[0])
    build = service.get("build", {})
    dockerfile = build.get("dockerfile") if isinstance(build, dict) else None
    return "built from " + code(str(dockerfile or build)).replace("./", "")


def dependencies(service):
    depends = service.get("depends_on") or []
    return sorted(depends)


def main():
    block = load_section("ports")
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    check_stale("ports", block, services)

    published = []
    for name in sorted(services):
        for spec in services[name].get("ports") or []:
            host, variable, container, protocol = parse_port(spec)
            published.append(
                [
                    code(name),
                    code(host) if host else "assigned by Docker",
                    code(container),
                    protocol,
                    code(variable) if variable else "fixed",
                ]
            )

    rows = []
    for name in sorted(services):
        service = services[name]
        rows.append(
            [
                code(name),
                image_label(service),
                ", ".join(code(p) for p in service.get("profiles") or []) or "always",
                ", ".join(code(d) for d in dependencies(service)) or "none",
                description(block, name),
            ]
        )

    sections = [
        "## Published ports",
        table(["Service", "Host port", "Container port", "Protocol", "Host port set by"], published),
        "## Compose services",
        table(["Service", "Image", "Profile", "Depends on", "Description"], rows),
    ]
    write_page("ports.md", "Ports and services", "gen_ports.py", block, sections)


if __name__ == "__main__":
    main()

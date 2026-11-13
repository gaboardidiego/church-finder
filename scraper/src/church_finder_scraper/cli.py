"""Dispatch scraper commands to independent country implementations."""

from __future__ import annotations

import argparse
from importlib import import_module

COUNTRY_MODULES = {
    "austria": {
        "services": "church_finder_scraper.austria.cli",
    },
}


def dispatch(command: str, argv: list[str] | None = None) -> int:
    countries = tuple(
        country for country, commands in COUNTRY_MODULES.items() if command in commands
    )
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument(
        "--country",
        choices=countries,
        default="austria",
        help="country implementation (default: austria)",
    )
    args, remaining = parser.parse_known_args(argv)
    parser.set_defaults(country=args.country)
    module = import_module(COUNTRY_MODULES[args.country][command])
    return module.run(remaining, parent_parser=parser)


def services() -> int:
    return dispatch("services")

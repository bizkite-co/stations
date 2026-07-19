"""stations CLI — currently ``stations inspect`` (read-only)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stations",
        description="Stations substrate tools (inspect is read-only).",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print package version and exit",
    )
    sub = parser.add_subparsers(dest="command")

    inspect_p = sub.add_parser(
        "inspect",
        help="Read-only render of a conforming station root",
    )
    inspect_p.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Station root or parent directory (local path). Default: cwd",
    )
    inspect_p.add_argument(
        "--plain",
        action="store_true",
        help="Plain text output (no Rich)",
    )
    inspect_p.add_argument(
        "--no-leases",
        action="store_true",
        help="Skip lease JSON content parsing (structure counts only)",
    )
    inspect_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from stations import __version__

        print(__version__)
        return 0

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "inspect":
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.WARNING,
            format="%(levelname)s %(name)s: %(message)s",
        )
        root = str(Path(args.root).expanduser().resolve())
        if not Path(root).exists():
            logging.error("path does not exist: %s", root)
            return 2
        from stations.inspect import inspect_and_render

        inspect_and_render(
            root,
            parse_leases=not args.no_leases,
            plain=args.plain,
        )
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

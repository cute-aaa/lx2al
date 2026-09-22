"""CLI: python -m lxmc2alcfg <input.lxmc> -o <output.alcfg>"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .converter import convert_file, load_lx_data, detect_lx_type

log = logging.getLogger("lxmc2alcfg")


def _count_songs(data: dict) -> tuple[int, dict[str, int]]:
    d = data["songlist"]["data"]
    per = {
        "defaultList": d["defaultList"]["meta"]["songCount"],
        "loveList": d["loveList"]["meta"]["songCount"],
        "userList": sum(item["meta"]["songCount"] for item in d["userList"]),
    }
    return sum(per.values()), per


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lxmc2alcfg",
        description=(
            "Convert lx-music backup (.lxmc/.json: allData_v2 / playList_v2 / legacy) "
            "into any-listen songlist backup (.alcfg)."
        ),
    )
    p.add_argument("input", type=Path, help="lx-music export file (.lxmc or .json, gzip or plain)")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="output path (default: <input stem>.alcfg next to input)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="write plain JSON instead of gzip .alcfg",
    )
    p.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print JSON output (only with --json)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="parse and convert in memory only; print summary, do not write",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    p.add_argument("--version", action="version", version=f"lxmc2alcfg {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    src: Path = args.input
    if not src.is_file():
        log.error("input not found: %s", src)
        return 2

    out: Path = args.output
    if out is None:
        suffix = ".json" if args.json else ".alcfg"
        out = src.with_name(src.stem + ".converted" + suffix)

    try:
        lx = load_lx_data(src)
        lx_type = detect_lx_type(lx)
        log.info("input type=%s file=%s", lx_type or "(none)", src)
        if args.dry_run:
            from .converter import convert

            data = convert(lx)
        else:
            data = convert_file(src, out, pretty=args.pretty, gzip_out=not args.json)
            log.info("wrote %s", out)
    except Exception as exc:
        log.error("convert failed: %s", exc)
        if args.verbose:
            log.exception("detail")
        return 1

    total, per = _count_songs(data)
    user = data["songlist"]["data"]["userList"]
    log.info(
        "songs total=%s (default=%s love=%s userLists=%s/%s)",
        total,
        per["defaultList"],
        per["loveList"],
        len(user),
        per["userList"],
    )
    for item in user:
        log.info(
            "  user list [%s] %r: %s songs",
            item["id"],
            item["name"],
            item["meta"]["songCount"],
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

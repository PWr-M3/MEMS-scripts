import argparse
from pathlib import Path


import mems.library.install as install
import mems.library.fill as fill
import mems.library.cap_csv as cap_csv
import mems.library.res_csv as res_csv

import logging

logger = logging.getLogger(__name__)


def add_subparser(parser: argparse.ArgumentParser):
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    fill_parser = subparsers.add_parser(name="fill", help="Fills in missing fields in library")
    fill_parser.add_argument("path", help="Specifies path to symbol library file")

    install_parser = subparsers.add_parser(name="install", help="Installs library in specified directory")
    install_parser.add_argument("path", type=Path)

    _ = subparsers.add_parser(name="update", help="Updates library from git")

    _ = subparsers.add_parser(name="cap_csv", help="Regenerate capacitors based on csv")
    _ = subparsers.add_parser(name="res_csv", help="Regenerate resistors based on csv")

    parser.set_defaults(func=run)


def run(args: argparse.Namespace):
    if args.subcommand == "fill":
        fill.Library(args).run()
    if args.subcommand == "install":
        assert isinstance(args.path, Path)
        install.install_lib(args.path)
    if args.subcommand == "update":
        logger.info("Running library update")
        install.update_from_git()
        install.configure_kicad()
    if args.subcommand == "cap_csv":
        cap_csv.regenerate()
    if args.subcommand == "res_csv":
        res_csv.regenerate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_subparser(parser)
    args = parser.parse_args()
    run(args)

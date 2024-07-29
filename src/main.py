import argparse
import logging
import sane_logging

from mems import bom, consolidate, utils, suppliers
from mems.library import library

logger = logging.getLogger(__name__)


def test(_):
    print("test")


def main():
    parser = argparse.ArgumentParser(prog="MEMS Scripts")
    parser.add_argument(
        "-l", "--log", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], dest="log_level", default="INFO"
    )

    subparsers = parser.add_subparsers(required=True, help="Subcommand")

    parser_test = subparsers.add_parser("test", help="Testing function, used for debugging")
    parser_test.set_defaults(func=test)

    parser_bom = subparsers.add_parser("bom", help="Generate bom and do bom checks")
    bom.add_subparser(parser_bom)

    parser_consolidate = subparsers.add_parser("consolidate", help="Consolidate component lists into a single list")
    consolidate.add_subparser(parser_consolidate)

    parser_library = subparsers.add_parser("library", help="Helper functions for library maintanance")
    library.add_subparser(parser_library)

    args = parser.parse_args()

    if logger.parent is not None:
        sane_logging.SaneLogging().terminal(args.log_level).file(utils.get_data_dir() / "logs").apply(logger.parent)
    logger.info("MEMS Scripts started")

    args.func(args)


if __name__ == "__main__":
    main()

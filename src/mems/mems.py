import argparse
import logging
import sane_logging

from mems import bom, consolidate, library, utils

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(prog="MEMS Scripts")
    parser.add_argument(
        "-l", "--log", choices=["DEBUG", "INFO", "WARNIGN", "ERROR", "CRITICAL"], dest="log_level", default="INFO"
    )

    subparsers = parser.add_subparsers(required=True, help="Subcommand")

    parser_bom = subparsers.add_parser("bom", help="Generate bom and do bom checks")
    bom.add_subparser(parser_bom)

    parser_consolidate = subparsers.add_parser("consolidate", help="Consolidate component lists into a single list")
    consolidate.add_subparser(parser_consolidate)

    parser_library = subparsers.add_parser("library", help="Helper functions for library maintanance")
    library.add_subparser(parser_library)

    args = parser.parse_args()

    sane_logging.SaneLogging().terminal(args.log_level).file(utils.get_data_dir() / "logs").apply(logger)
    logger.info("MEMS Scripts started")

    args.func(args)


if __name__ == "__main__":
    main()

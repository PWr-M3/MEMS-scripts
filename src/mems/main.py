import argparse
import logging
import sane_logging
import git
import sys
import pathlib

from mems import bom, consolidate, utils, variable, outputs
from mems.library import library

logger = logging.getLogger(__name__)


def check_if_up_to_date():
    repo = git.Repo(pathlib.Path(__file__), search_parent_directories=True)
    if repo.is_dirty():
        logger.error("Script repository is dirty. Exiting. Check is ignored with '-l DEBUG'.")
        sys.exit(1)
    remote = repo.head.reference.tracking_branch()
    if not isinstance(remote, git.RemoteReference):
        logger.error("Tracking branch not set for script repository. Exiting. Check is ignored with '-l DEBUG'.")
    if remote.commit != repo.head.commit: # type: ignore
        logger.error("Script is not up to date. Pull data from origin. Check is ignored with '-l DEBUG'.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(prog="MEMS Scripts")
    parser.add_argument(
        "-l", "--log", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], dest="log_level", default="INFO"
    )
    subparsers = parser.add_subparsers(required=True, help="Subcommand")

    bom.add_subparser(subparsers)
    consolidate.add_subparser(subparsers)
    library.add_subparser(subparsers)
    variable.add_subparser(subparsers)
    outputs.add_subparser(subparsers)

    args = parser.parse_args()


    if logger.parent is not None:
        sane_logging.SaneLogging().terminal(args.log_level).file(utils.get_data_dir() / "logs").apply(logger.parent)
    logger.info("MEMS Scripts started")

    if (args.log_level != "DEBUG"):
        check_if_up_to_date()

    args.func(args)


if __name__ == "__main__":
    main()

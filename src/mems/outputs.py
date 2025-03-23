import logging
import subprocess
import pathlib
import sys
import git
import os
import datetime

from mems import utils

logger = logging.getLogger(__name__)

JOBSET_FILENAME = "mems.kicad_jobset"

def add_subparser(subparsers):
    parser = subparsers.add_parser("outputs", help="Generate fabrication outputs")
    parser.add_argument("revision", help="Revision name to tag the outputs")
    parser.set_defaults(func=generate_outputs)

def set_sha(repo: git.Repo):
    sha = repo.head.object.hexsha[:7]
    logger.info(f"Current HEAD SHA is: {sha}. Updating project variable")
    utils.set_text_variable("SHA", sha)

def create_release_branch(repo: git.Repo, version: str):
    branch = repo.create_head(f"release/{version}")
    repo.head.reference = branch
    repo.head.reset(index=True, working_tree=True)

def generate_outputs(args):
    revision = args["revision"]

    repo = git.Repo(os.getcwd())

    utils.check_repo_clean(repo)

    create_release_branch(repo, revision)

    logger.info("Updating text variables")
    set_sha(repo)
    utils.set_text_variable("rev", revision)
    utils.set_text_variable("date", datetime.datetime.now().strftime("%Y-%m-%d"))

    logger.info("Running jobs")
    jobfile = (pathlib.Path(__file__).parent.parent.parent / JOBSET_FILENAME).resolve()
    pro_file = utils.get_pro_filename()
    if pro_file is None:
        sys.exit(1)

    ret_code = subprocess.Popen([
            "kicad-cli",
            "jobset",
            "run",
            "--stop-on-error",
            "-f",
            jobfile,
            pro_file
        ],
        cwd=pro_file.parent,
        stdout=sys.stdout,
        stderr=sys.stderr,
    ).communicate()

    if ret_code != 0:
        logger.error("Failed running jobset")
        return ret_code

    logger.info("Commiting created files")
    repo.index.add(".")
    repo.index.commit(f"Relase of rev. {revision}")

    logger.warning("Remember to push new branch to origin")



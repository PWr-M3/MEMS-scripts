import datetime
import logging
import os
import pathlib
import shutil
import subprocess
import sys
from importlib import resources

import git

from mems import utils
from mems.release import bom

logger = logging.getLogger(__name__)

def add_subparser(subparsers):

    parser = subparsers.add_parser("release", help="Tools used for release")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    all_parser = subparsers.add_parser(name="all", help="Create a new release. To be used when ordering boards")
    all_parser.add_argument("revision", help="Revision name to tag the outputs, e.g. 1.0")

    variables_parser = subparsers.add_parser(name="variables", help="Fill in release variables such as SHA, date and revision")
    variables_parser.add_argument("revision", help="Revision name to tag the outputs, e.g. 1.0")

    _ = subparsers.add_parser(name="check", help="Perform checks that need to pass for release")
    _ = subparsers.add_parser(name="jlcpcb", help="Generate outputs for JLCPCB pcb fabrication")
    _ = subparsers.add_parser(name="pdf", help="Generate schematic pdf")

    bom.add_subparser(subparsers)

    parser.set_defaults(func=run)

def run(args) -> None:
    if args.subcommand == "set_variables":
        set_variables(args.revision)
    if args.subcommand == "check":
        check()
    if args.subcommand == "bom":
        bom.run()
    if args.subcommand == "all":
        run_all(args)
    if args.subcommand == "jlcpcb":
        jlcpcb()
    if args.subcommand == "pdf":
        pdf()


def set_variables(revision: str):
    logger.info("Updating text variables")
    repo = git.Repo(os.getcwd(), search_parent_directories=True)
    set_sha(repo)
    utils.set_text_variable("rev", revision)
    utils.set_text_variable("date", datetime.datetime.now().strftime("%Y-%m-%d"))

def set_sha(repo: git.Repo):
    sha = repo.head.object.hexsha[:7].upper()
    logger.info(f"Current HEAD SHA is: {sha}. Updating project variable")
    utils.set_text_variable("sha", sha)


def check(clean=True):
    ok = True
    pro_file = utils.get_pro_filename()
    if pro_file is None:
        sys.exit(1)

    logger.info("Running Electrical Rule Check")
    retcode = run_jobset("erc.kicad_jobset")
    if retcode != 0:
        logger.error("ERC failed")
        with open(pro_file.parent / "fab/ERC.txt") as erc:
            logger.error(f"ERC report: \n{erc.read()}")
        ok = False
    else:
        logger.info("ERC passed")

    logger.info("Running Design Rule Check")
    retcode = run_jobset("drc.kicad_jobset")
    if retcode != 0:
        logger.error("DRC failed")
        with open(pro_file.parent / "fab/DRC.txt") as drc:
            logger.error(f"DRC report: \n{drc.read()}")
        ok = False
    else:
        logger.info("DRC passed")

    logger.info("Running BOM Check")
    bom_obj = bom.BOM()
    bom_obj.run()
    
    if bom_obj.has_errored:
        logger.error("BOM failed")
        ok = False

    if ok:
        logger.info("Everything seems to be ok")
    else:
        logger.error("Some of the checks didn't pass")

    if clean:
        shutil.rmtree(pro_file.parent / "fab")

    return ok

def jlcpcb():
    ret = run_jobset("jlcpcb.kicad_jobset")
    if ret != 0:
        logger.error("Failed creating JLCPCB outputs")
    return ret

def pdf():
    ret = run_jobset("pdf.kicad_jobset")
    if ret != 0:
        logger.error("Failed creating PDF output")
    return ret

def run_jobset(name: str):
    pro_file = utils.get_pro_filename()
    if pro_file is None:
        sys.exit(1)

    with resources.as_file(resources.files("mems.data")) as path:
        path = pathlib.Path(path)

        completed = subprocess.run(
            ["kicad-cli", "jobset", "run", "--stop-on-error", "-f", str(path / name), str(pro_file)],
            cwd=pro_file.parent,
        )
        if completed.returncode != 0:
            logger.error("Failed running jobset")

        return completed.returncode

def create_release_branch(repo: git.Repo, release_branch_name: str) -> git.Reference:
    if release_branch_name in repo.heads:
        logger.error("Release with this version already exists")
        sys.exit(1)
    branch = repo.create_head(release_branch_name)
    repo.head.reference = branch
    repo.head.reset(index=True, working_tree=True)
    return branch

def check_branch_is_main(repo):
    if repo.active_branch.name != "main":
        logger.error("Current branch is not main. Releases are allowed only from main")
        sys.exit(1)

def cleanup(repo, release_branch_name):
    main_branch = repo.heads.main
    repo.head.reference = main_branch
    repo.head.reset(index=True, working_tree=True)
    repo.delete_head(release_branch_name)
    shutil.rmtree(utils.get_pro_filename().parent / "fab")
    sys.exit(1)

def run_all(args):
    release_branch_name = f"release/{args.revision}"
    repo = git.Repo(os.getcwd(), search_parent_directories=True)

    utils.check_repo_clean(repo)
    check_branch_is_main(repo)
    create_release_branch(repo, release_branch_name)

    try:

        set_variables(args.revision)

        ok = check(clean=False)
        if not ok:
            cleanup(repo, release_branch_name)

        ret = jlcpcb()
        if ret != 0:
            cleanup()

        ret = pdf()
        if ret != 0:
            cleanup()

        bom_obj = bom.BOM()
        bom_obj.run()
        if bom_obj.has_errored:
            cleanup()

        logger.info("Commiting created files")
        repo.git.add(".")
        repo.git.add(utils.get_pro_filename().parent / "fab" / "*", force=True)
        repo.index.commit(f"Relase of rev. {args.revision}")

        logger.warning("Remember to push new branch to origin")


    except:
        cleanup(repo, release_branch_name)


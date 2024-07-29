import logging
import xdg
import sys
import git
from pathlib import Path

import kiutils.symbol

logger = logging.getLogger(__name__)

LIBRARY_RESOURCE_NAME = "MEMSComponents"


def get_lib_path() -> Path | None:
    """Returns path to library in data directory or None if not found."""
    paths = xdg.BaseDirectory.load_data_paths(LIBRARY_RESOURCE_NAME)
    try:
        return Path(next(paths)).resolve()
    except StopIteration:
        return None


def get_lib_repo() -> git.Repo:
    """Returns repository of components"""
    path = get_lib_path()
    if path is None:
        logger.error("Cannot open library repository as it isn't installed. Install with 'mems library install'")
        sys.exit(1)
    return git.Repo(path)


def check_repo_clean(repo: git.Repo):
    """Stops program if repo is not clean."""
    if repo.is_dirty(untracked_files=True):
        logger.error("Repository is dirty. Aborting. Commit all changes before proceeding.")
        sys.exit(1)
    logger.debug("Repo is clean. Proceeding")


def commit_lib_repo(repo: git.Repo, message: str):
    """Commits all changes in the repo."""
    repo.git.add(all=True)
    repo.index.commit(message)
    logger.warn("Changes commited to repository. Remember to push them to origin.")


def load_symbol_library(name: str) -> kiutils.symbol.SymbolLib:
    """Loads MEMS symbol library from standard install path to kiutils object."""
    path = get_lib_path()
    if path is None:
        logger.error("Library is not installed. Install with 'mems library install <path>'")
        sys.exit(1)
    path = (path / "symbols" / name).with_suffix(".kicad_sym")
    if path.exists():
        logger.info(f"Loading symbol library: {path}")
        return kiutils.symbol.SymbolLib.from_file(str(path))

    logger.error(f"Following symbol library doesn't exist: {path}")
    sys.exit(1)

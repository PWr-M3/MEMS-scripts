from pathlib import Path
import logging
import sys
import os
import json
import git
import xdg
import kiutils.libraries

logger = logging.getLogger(__name__)

URL = "git@github.com:PWr-M3/MEMSComponents.git"
RESOURCE_NAME = "MEMSComponents"
KICAD_RESOURCE_NAME = "kicad"
SYMBOL_SHORTHAND = "MEMS_SYMBOLS"
FOOTPRINT_SHORTHAND = "MEMS_FOOTPRINTS"
MODEL_SHORTHAND = "MEMS_3DMODELS"

LIBRARY_NOT_INSTALLED_MSG = "Library is not installed. Run 'mems library install'."


def install_lib(path: Path):
    """Clones library repository, symlinks it to data_dir and configures kicad to use it."""
    path = path / "MEMSComponents"
    if get_lib_path() is not None:
        logger.error("Library is already installed (symlinked in data dircetory)")
        sys.exit(1)
    if path.exists():
        logger.error("MEMSComponents already exists in passed directory")
        sys.exit(1)

    logger.info(f"Cloning library from {URL}")
    _ = git.Repo.clone_from(URL, path)
    symlink_path = Path(xdg.BaseDirectory.xdg_data_dirs[0]) / RESOURCE_NAME
    if not os.path.lexists(symlink_path):
        logger.info(f"Symlinking library to: {symlink_path}")
        os.symlink(path.resolve(), symlink_path, target_is_directory=True)

    configure_kicad()


def get_lib_path() -> Path | None:
    """Returns path to library in data directory or None if not found."""
    paths = xdg.BaseDirectory.load_data_paths(RESOURCE_NAME)
    try:
        return Path(next(paths)).resolve()
    except StopIteration:
        return None


def get_kicad_config_path() -> Path:
    """Returns path to kicad config directory."""
    paths = xdg.BaseDirectory.load_config_paths(KICAD_RESOURCE_NAME)
    try:
        return Path(next(paths)).resolve()
    except StopIteration:
        sys.exit("Kicad config not found. Make sure you run it")


def configure_kicad():
    """Adds library to kicad config, or updates if already added."""
    logger.info("Setting up kicad with library")
    path = get_kicad_config_path()
    for directory in path.iterdir():
        setup_kicad_paths(directory / "kicad_common.json")
        add_symbol_libs(directory / "sym-lib-table")
        add_footprint_libs(directory / "fp-lib-table")


def add_symbol_libs(sym_lib_path: Path):
    logger.info("Loading symbol library table")
    sym_lib = kiutils.libraries.LibTable.from_file(str(sym_lib_path))
    sym_lib.libs[:] = [lib for lib in sym_lib.libs if SYMBOL_SHORTHAND not in lib.uri]
    lib_path = get_lib_path()
    if lib_path is None:
        sys.exit("Library is not installed")
    for path in (lib_path / "symbols").iterdir():
        if path.suffix == ".kicad_sym":
            sym_lib.libs.append(kiutils.libraries.Library(name=path.stem, uri=f"${{{SYMBOL_SHORTHAND}}}/{path.name}"))
    sym_lib.to_file()
    logger.info("Symbol library table updated and saved")


def add_footprint_libs(fp_lib_path: Path):
    logger.info("Loading footprint library table")
    fp_lib = kiutils.libraries.LibTable.from_file(str(fp_lib_path))
    fp_lib.libs[:] = [lib for lib in fp_lib.libs if FOOTPRINT_SHORTHAND not in lib.uri]
    lib_path = get_lib_path()
    if lib_path is None:
        sys.exit("Library is not installed")
    for path in (lib_path / "footprints").iterdir():
        if path.suffix == ".kicad_mod":
            fp_lib.libs.append(kiutils.libraries.Library(name=path.stem, uri=f"${{{FOOTPRINT_SHORTHAND}}}/{path.name}"))
    fp_lib.to_file()
    logger.info("Footprint library table updated and saved")


def setup_kicad_paths(kicad_common_path: Path):
    logger.info("Loading kicad_common.json config file")
    content = {}
    try:
        with open(kicad_common_path, "r") as f:
            content = json.load(f)
    except IOError as error:
        logger.error(f"Failed to read file: {kicad_common_path}. Error: {error}")
        sys.exit(1)
    if "environment" not in content:
        content["environment"] = {}
    if "vars" not in content["environment"]:
        content["environment"]["vars"] = {}
    var = content["environment"]["vars"]

    lib_path = get_lib_path()
    if lib_path is None:
        logger.error(LIBRARY_NOT_INSTALLED_MSG)
        sys.exit(1)

    logger.info("Appending paths to config.")

    var[SYMBOL_SHORTHAND] = str(lib_path / "symbols")
    var[FOOTPRINT_SHORTHAND] = str(lib_path / "footprints")
    var[MODEL_SHORTHAND] = str(lib_path / "3d_models")

    try:
        with open(kicad_common_path, "w") as f:
            json.dump(content, f)
    except IOError as error:
        logger.error(f"Failed to read file: {kicad_common_path}. Error: {error}")
        sys.exit(1)

    logger.info("Changes saved to kicad_common.json")


def update_from_git():
    lib_path = get_lib_path()
    if lib_path is None:
        logger.error(LIBRARY_NOT_INSTALLED_MSG)
        sys.exit(1)

    repo = git.Repo(lib_path)
    if repo.is_dirty(untracked_files=True):
        logger.error("Repository is dirty. Aborting. Commit all changes before proceeding.")
        sys.exit(1)

    logger.info("Pulling latest changes from origin.")
    repo.remotes.origin.pull()
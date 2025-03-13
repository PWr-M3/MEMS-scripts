from pathlib import Path
import logging
import sys
import os
import json
import git
import xdg
import kiutils.libraries

from mems.library.lib_utils import LIBRARY_RESOURCE_NAME, get_lib_path, get_lib_repo, check_repo_clean

logger = logging.getLogger(__name__)

URL = "git@github.com:PWr-M3/MEMSComponents.git"
KICAD_RESOURCE_NAME = "kicad"
SYMBOL_SHORTHAND = "MEMS_SYMBOLS"
FOOTPRINT_SHORTHAND = "MEMS_FOOTPRINTS"
MODEL_SHORTHAND = "MEMS_3DMODELS"

LIBRARY_NOT_INSTALLED_MSG = "Library is not installed. Run 'mems library install'."


def install_lib(path: Path):
    """Clones library repository, symlinks it to data_dir and configures kicad to use it."""
    path = path / "MEMSComponents"


    if get_lib_path() is None:
        logger.error("Library not symlinked. Downloading and symlinking")
        
        if path.exists():
            logger.error("MEMSComponents already exists in passed directory.")
            sys.exit(1)

        logger.info(f"Cloning library from {URL}")
        _ = git.Repo.clone_from(URL, path)
        symlink_path = Path(xdg.BaseDirectory.xdg_data_dirs[0]) / LIBRARY_RESOURCE_NAME
        if not os.path.lexists(symlink_path):
            logger.info(f"Symlinking library to: {symlink_path}")
            os.symlink(path.resolve(), symlink_path, target_is_directory=True)

    configure_kicad()


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
    path = get_kicad_config_path() / "9.0"
    setup_kicad_common(path / "kicad_common.json")
    add_symbol_libs(path / "sym-lib-table")
    add_footprint_libs(path / "fp-lib-table")


def add_symbol_libs(sym_lib_path: Path):
    logger.info("Loading symbol library table")
    sym_lib = kiutils.libraries.LibTable.from_file(str(sym_lib_path))
    sym_lib.libs[:] = [lib for lib in sym_lib.libs if SYMBOL_SHORTHAND not in lib.uri]
    lib_path = get_lib_path()
    if lib_path is None:
        sys.exit("Library is not installed")
    for path in (lib_path / "symbols").iterdir():
        if path.suffix == ".kicad_sym":
            uri = f"${{{SYMBOL_SHORTHAND}}}/{path.name}"
            sym_lib.libs.append(kiutils.libraries.Library(name=path.stem, uri=uri))
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
        if path.suffix == ".pretty":
            uri = f"${{{FOOTPRINT_SHORTHAND}}}/{path.name}"
            fp_lib.libs.append(kiutils.libraries.Library(name=path.stem, uri=uri))
    fp_lib.to_file()
    logger.info("Footprint library table updated and saved")


def setup_kicad_common(kicad_common_path: Path):
    logger.info("Loading kicad_common.json config file")
    content = {}
    try:
        with open(kicad_common_path, "r") as f:
            content = json.load(f)
    except IOError as error:
        logger.error(f"Failed to read file: {kicad_common_path}. Error: {error}")
        sys.exit(1)
    if "environment" not in content or content["environment"] is None:
        content["environment"] = {}
    if "vars" not in content["environment"] or content["environment"]["vars"] is None:
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

    logger.info("Pinning symbol libs.")

    pinned_symbol_libs = content["session"]["pinned_symbol_libs"]
    pinned_symbol_libs = list(filter(lambda x: "MEMS_" in x, pinned_symbol_libs))

    lib_path = get_lib_path()
    if lib_path is None:
        sys.exit("Library is not installed")
    for path in (lib_path / "symbols").iterdir():
        if path.suffix == ".kicad_sym":
            pinned_symbol_libs.append(path.stem)

    content["session"]["pinned_symbol_libs"] = pinned_symbol_libs

    logger.info("Pinning footprint libs")

    pinned_fp_libs = content["session"]["pinned_fp_libs"]
    pinned_fp_libs = list(filter(lambda x: "MEMS_" in x, pinned_fp_libs))

    lib_path = get_lib_path()
    if lib_path is None:
        sys.exit("Library is not installed")
    for path in (lib_path / "footprints").iterdir():
        if path.suffix == ".pretty":
            print(path.stem)
            pinned_fp_libs.append(path.stem)

    content["session"]["pinned_fp_libs"] = pinned_fp_libs

    try:
        with open(kicad_common_path, "w") as f:
            json.dump(content, f)
    except IOError as error:
        logger.error(f"Failed to save file: {kicad_common_path}. Error: {error}")
        sys.exit(1)

    logger.info("Changes saved to kicad_common.json")


def update_from_git():
    repo = get_lib_repo()
    check_repo_clean(repo)

    logger.info("Pulling latest changes from origin.")
    repo.remotes.origin.pull()

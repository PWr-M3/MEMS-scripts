import argparse
import json
import os
import sys
import time
from pathlib import Path

import colorama
import git
import kiutils.items
import kiutils.items.common
import kiutils.libraries
import kiutils.symbol
import termcolor
import xdg.BaseDirectory

from mems import utils

import logging

logger = logging.getLogger(__name__)

URL = "git@github.com:PWr-M3/MEMSComponents.git"
RESOURCE_NAME = "MEMSComponents"
KICAD_RESOURCE_NAME = "kicad"
SYMBOL_SHORTHAND = "MEMS_SYMBOLS"
FOOTPRINT_SHORTHAND = "MEMS_FOOTPRINTS"
MODEL_SHORTHAND = "MEMS_3DMODELS"

LIBRARY_NOT_INSTALLED_MSG = "Library is not installed. Run 'mems library install'."


def add_subparser(parser: argparse.ArgumentParser):
    subparsers = parser.add_subparsers(dest="subcommand")
    fill_parser = subparsers.add_parser(name="fill", help="Fills in missing fields in library")
    fill_parser.add_argument("path", help="Specifies path to symbol library file")
    fill_parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Verbose mode",
    )

    install_parser = subparsers.add_parser(name="install", help="Installs library in specified directory")
    install_parser.add_argument("path", type=Path)

    _ = subparsers.add_parser(name="update", help="Updates library from git")

    parser.set_defaults(func=run)


def run(args: argparse.Namespace):
    if args.subcommand == "fill":
        Library(args).run()
    if args.subcommand == "install":
        assert isinstance(args.path, Path)
        install_lib(args.path)
    if args.subcommand == "update":
        logger.info("Running library update")
        update_from_git()
        configure_kicad()


class Library:
    def __init__(self, args):
        self.args = args
        self.path = self.get_path()
        self.config = utils.get_config()
        self.sym_lib = None

    def run(self):
        colorama.just_fix_windows_console()

        self.open_sym_lib()

        if self.args.fill:
            self.fill_fields()

        self.save_sym_lib()

    def open_sym_lib(self):
        self.sym_lib = kiutils.symbol.SymbolLib.from_file(self.path)

    def save_sym_lib(self):
        if self.sym_lib is not None:
            self.sym_lib.to_file(self.path)

    def get_path(self):
        if self.args.path is not None and not os.path.exists(self.args.path):
            sys.exit(termcolor.colored(f"Error: Specified filename isn't correct ({self.args.path})", "red"))
        else:
            path = self.args.path
        return path

    def fill_fields(self):
        # Right now it updates all components. Maybe change it so it checks whether any property needs updating
        if self.sym_lib is not None:
            print("Filling missing fields")
            for symbol in self.sym_lib.symbols:
                mouser = self.find_property(symbol, "Mouser")
                mpn = self.find_property(symbol, "MPN")
                tme = self.find_property(symbol, "TME")
                reference = self.find_property(symbol, "Reference")
                datasheet = self.find_property(symbol, "Datasheet")

                if reference == "#PWR":  # ignore power symbols
                    continue

                if self.args.verbose:
                    print(symbol.entryName)

                no_missing_values = True
                for test in [datasheet, mpn, mouser]:
                    if test is not None:
                        if test.value.strip() == "" or test.value.strip() == "~":
                            no_missing_values = False
                    else:
                        no_missing_values = False

                if no_missing_values:
                    continue

                if mouser is not None:
                    mouser.value = mouser.value.strip()
                    result = None
                    while result is None:
                        result = utils.search_mouser(mouser.value)
                        if result["Errors"] == []:
                            break
                        if result["Errors"][0]["Code"] == "TooManyRequests":
                            print(termcolor.colored("Max requests per minute reached, waiting", "white"))
                            time.sleep(2)

                    part = self.find_matching_part(result, "MouserPartNumber", mouser.value)
                    if part is None:
                        if not tme:
                            print(
                                termcolor.colored(
                                    f'{symbol.entryName}: Mouser ID "{mouser.value}" not found on Mouser!', "red"
                                )
                            )
                        continue
                elif mpn is not None:
                    mpn.value = mpn.value.strip()
                    if mpn.value == "NO_MPN":
                        continue
                    result = utils.search_mouser(mpn.value)
                    part = self.find_matching_part(result, "ManufacturerPartNumber", mpn.value)
                    if part is None:
                        if not tme:
                            print(
                                termcolor.colored(f'{symbol.entryName}: MPN "{mpn.value}" not found on Mouser!', "red")
                            )
                        continue
                else:
                    print(termcolor.colored(f"{symbol.entryName}: Both MPN and Mouser fields missing!", "red"))
                    continue

                self.set_property(symbol, "MPN", part["ManufacturerPartNumber"])
                self.find_property(symbol, "MPN").effects.hide = True  # type: ignore Just created so must exist
                self.set_property(symbol, "Mouser", part["MouserPartNumber"])
                self.find_property(symbol, "Mouser").effects.hide = True  # type: ignore Just created so must exist
                self.set_property(symbol, "ki_description", part["Description"])
                self.set_property(symbol, "Datasheet", part["DataSheetUrl"])
                self.find_property(symbol, "Datasheet").effects.hide = True  # type: ignore Just created so must exist

    def find_property(self, symbol, name):
        return next((prop for prop in symbol.properties if prop.key == name), None)

    def set_property(self, symbol, name, value, overwrite=False):
        done = False

        for prop in symbol.properties:
            if prop.key == name:
                done = True
                if overwrite or prop.value in ["", "~"]:
                    prop.value = value
                    if self.args.verbose:
                        print(termcolor.colored(f"SETTING {name} to {value}", "green"))

        if not done:
            new = kiutils.items.common.Property(key=name, value=value)
            new.effects = kiutils.items.common.Effects()
            symbol.properties.append(new)

    def find_matching_part(self, response, key, value):
        try:
            return next(
                (part for part in response["SearchResults"]["Parts"] if key in part and part[key] == value),
                None,
            )
        except TypeError:
            print(termcolor.colored("Empty response", "red"))
            print(response)
            return None


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
        logger.error("Repository is dirty. Aborting. Commit all changes.")
        sys.exit(1)

    logger.info("Pulling latest changes from origin.")
    repo.remotes.origin.pull()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_subparser(parser)
    args = parser.parse_args()
    run(args)

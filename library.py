import argparse
import os
import sys
from typing import Tuple
import pathlib
import json

import colorama
import termcolor
import kiutils.symbol
import kiutils.items
import requests

import utils


def add_subparser(parser: argparse.ArgumentParser):
    parser.add_argument(
        "path",
        help="Specifies path to symbol library file",
    )
    parser.add_argument(
        "-f",
        "--fill-in",
        dest="fill",
        action="store_true",
        help="Fills in missing fields in library",
    )
    parser.set_defaults(func=run)


def run(args):
    Library(args).run()


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
            sys.exit(
                termcolor.colored(
                    f"Error: Specified filename isn't correct ({self.args.path})", "red"
                )
            )
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
                if mouser is not None:
                    result = utils.search_mouser(mouser)
                    part = self.find_matching_part(result, "MouserPartNumber", mouser)
                elif mpn is not None:
                    result = utils.search_mouser(mpn)
                    part = self.find_matching_part(
                        result, "ManufacturerPartNumber", mpn
                    )
                self.set_property(symbol, "MPN", part["ManufacturerPartNumber"])
                self.set_property(symbol, "Mouser", part["MouserPartNumber"])
                self.set_property(symbol, "ki_description", part["Description"])
                self.set_property(symbol, "Datasheet", part["DataSheetUrl"])

    def find_property(self, symbol, name):
        return next(
            (prop.value for prop in symbol.properties if prop.key == name), None
        )

    def set_property(self, symbol, name, value, overwrite=False):
        done = False
        for prop in symbol.properties:
            if prop.key == name:
                if overwrite or prop.value in ["", "~"]:
                    prop.value = value
                    done = True
        if not done:
            new = kiutils.items.common.Property(key=name, value=value)
            symbol.properties.append(new)

    def find_matching_part(self, response, key, value):
        return next(
            (
                part
                for part in response["SearchResults"]["Parts"]
                if key in part and part[key] == value
            ),
            None,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_subparser(parser)
    args = parser.parse_args()
    run(args)

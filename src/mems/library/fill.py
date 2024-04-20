import os
import sys
import time
from mems import utils
import kiutils.items
import kiutils.items.common
import kiutils.libraries
import kiutils.symbol
import logging

logger = logging.getLogger(__name__)


class Library:
    def __init__(self, args):
        self.args = args
        self.path = self.get_path()
        self.config = utils.get_config()
        self.sym_lib = None

    def run(self):

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
            logger.error(f"Specified filename isn't correct ({self.args.path})")
            sys.exit(1)
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
                            logger.warn("Max requests per minute reached, waiting")
                            time.sleep(2)

                    part = self.find_matching_part(result, "MouserPartNumber", mouser.value)
                    if part is None:
                        if not tme:
                            logger.error(f'{symbol.entryName}: Mouser ID "{mouser.value}" not found on Mouser!')
                        continue
                elif mpn is not None:
                    mpn.value = mpn.value.strip()
                    if mpn.value == "NO_MPN":
                        continue
                    result = utils.search_mouser(mpn.value)
                    part = self.find_matching_part(result, "ManufacturerPartNumber", mpn.value)
                    if part is None:
                        if not tme:
                            logger.error(f'{symbol.entryName}: MPN "{mpn.value}" not found on Mouser!')
                        continue
                else:
                    logger.error(f"{symbol.entryName}: Both MPN and Mouser fields missing!")
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
                        logger.info(f"SETTING {name} to {value}")

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
            logger.error("Empty response from Mouser")
            print(response)
            return None

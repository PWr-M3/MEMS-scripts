import argparse
import os
import sys
import csv

import colorama
import termcolor
from mems import utils


def run(args):
    Consolidate(args).run()


def add_subparser(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-p",
        "--path",
        dest="path",
        help="Specifies path to main schematic file",
    )
    parser.add_argument(
        "-s",
        "--spare",
        dest="spare",
        help="Number of spare components to add to every entry",
    )
    parser.set_defaults(func=run)


class Consolidate:
    def __init__(self, args):
        self.args = args
        self.file_list = self.get_file_list()
        self.spare = self.get_spares_count()
        self.has_errored = False
        self.bom = {}

    def run(self):
        colorama.just_fix_windows_console()

        for row in self.file_list:
            self.append_to_bom(row[0], row[1])

        self.generate_csv_bom()

        if self.has_errored:
            sys.exit(termcolor.colored("There were issues found", "red"))
        else:
            print("OK!")
            sys.exit()

    def append_to_bom(self, path, multiplier):
        with open(path, "r") as file:
            reader = csv.reader(file, delimiter=";")
            print(file)
            for row in reader:
                # if len(row) == 1:
                #    row = row[0].split(';')

                if row[1] == "SKU":
                    continue
                print(row)

                mpn = row[0]
                sku = row[1]
                quantity = int(row[2])
                price = row[3]
                in_stock = row[5]
                available = row[6]
                multiplier = int(multiplier)

                if sku not in self.bom.keys():
                    self.bom[sku] = {
                        "mpn": mpn,
                        "quantity": int(quantity * multiplier),
                        "price": price,
                        "in_stock": in_stock,
                        "available": available,
                        "board_needs": f"{path} ({quantity}x{multiplier})",
                    }
                else:
                    self.bom[sku]["quantity"] += int(quantity * multiplier)
                    self.bom[sku]["board_needs"] += f", {path} ({quantity}x{multiplier})"

    def get_file_list(self):
        path = utils.get_main_sch()
        if os.path.exists(path) and self.args.path is None:
            pass
        elif not os.path.exists(path) and self.args.path is None:
            sys.exit(
                termcolor.colored(
                    f"Error: Default filename doesn't exist ({path}) and alternative wasn't specified",
                    "red",
                )
            )
        elif self.args.path is not None and not os.path.exists(self.args.path):
            sys.exit(termcolor.colored(f"Error: Specified filename isn't correct ({self.args.path}", "red"))
        else:
            path = self.args.path
            data = []
            try:
                with open(path, "r") as file:
                    reader = csv.reader(file, delimiter=";")  # attempt semicolon separated
                    for row in reader:
                        a = row[1]
                        data.append(row)
            except IndexError:
                with open(path, "r") as file:
                    reader = csv.reader(file, delimiter=",")  # attempt comma separated
                    for row in reader:
                        a = row[1]
                        data.append(row)

        return data

    def generate_csv_bom(self):
        list_csv = [["MPN", "SKU", "Quantity", "Price [zł/unit]", "Price [zł]", "In stock", "Available", "Needed for"]]
        for part in self.bom.keys():
            try:
                print(self.bom[part]["price"], self.bom[part]["quantity"])
                price = float(self.bom[part]["price"]) * (self.spare + self.bom[part]["quantity"])

            except ValueError:
                price = 0

            list_csv.append(
                [
                    self.bom[part]["mpn"],
                    part,
                    self.bom[part]["quantity"] + self.spare,
                    self.bom[part]["price"],
                    price,
                    self.bom[part]["in_stock"],
                    self.bom[part]["available"],
                    self.bom[part]["board_needs"],
                ]
            )
        print(list_csv)
        with open("consolidated_bom.csv", "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(list_csv)

    def get_file_list(self):
        path = utils.get_main_sch()
        if os.path.exists(path) and self.args.path is None:
            pass
        elif not os.path.exists(path) and self.args.path is None:
            sys.exit(
                termcolor.colored(
                    f"Error: Default filename doesn't exist ({path}) and alternative wasn't specified",
                    "red",
                )
            )
        elif self.args.path is not None and not os.path.exists(self.args.path):
            sys.exit(termcolor.colored(f"Error: Specified filename isn't correct ({self.args.path}", "red"))
        else:
            path = self.args.path
            data = []
            with open(path, "r") as file:
                reader = csv.reader(file)
                for row in reader:
                    data.append(row)
        return data

    def get_spares_count(self):
        spare = self.args.spare
        try:
            return int(spare)
        except ValueError:
            return 0
        except TypeError:
            return 0

    def error(self, text):
        print(termcolor.colored("Error: " + text, "red"))
        self.has_errored = True

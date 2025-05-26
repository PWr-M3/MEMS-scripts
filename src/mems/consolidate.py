import argparse
import os
import sys
import csv
import numpy as np
import colorama
import termcolor
from mems import utils


def run(args):
    Consolidate(args).run()


def add_subparser(subparsers):
    parser = subparsers.add_parser("consolidate", help="Consolidate component lists into a single list")
    parser.add_argument(
        "-p",
        "--path",
        dest="path",
        help="Specifies path to csv file with two columns: location of main project file, and number of boards to be manufactured",
    )
    parser.add_argument(
        "-s",
        "--spares",
        dest="spares",
        help="Number of spare components to add to every ordered position, as csv file with two columns: price, and number of spares as fraction of ordered amount (to be rounded up) from that price up. ",
    )
    parser.add_argument(
        "-v",
        "--vendor",
        default="Mouser",
        dest="vendor",
        help="Vendor to be processed",
    )
    parser.set_defaults(func=run)


class Consolidate:
    def __init__(self, args):
        self.args = args
        self.file_list = self.get_file_list()
        self.has_errored = False
        self.bom = {}

    def run(self):
        colorama.just_fix_windows_console()
        vendor = self.args.vendor.strip()
        self.bom = {}

        for row in self.file_list:
            filename = f'{row[0]}/fab/bom/{vendor}.csv'
            multiplier = int(row[1])
            try:
                self.append_to_bom(filename, multiplier)
            except FileNotFoundError:
                pass

        self.generate_csv_bom(vendor)

        if self.has_errored:
            sys.exit(termcolor.colored("There were issues found", "red"))
        else:
            print("OK!")
            sys.exit()

    def append_to_bom(self, path, multiplier):
        with open(path, "r") as file:
            reader = csv.reader(file, delimiter=";")
            for row in reader:
                # if len(row) == 1:
                #    row = row[0].split(';')

                if row[1] == "SKU":
                    continue

                mpn = row[0]
                sku = row[1]
                quantity = int(row[2])
                price = row[3]
                in_stock = row[5]
                available = row[6]
                multiplier = int(multiplier)

                project_name = path.split('/')[-5]

                if sku not in self.bom.keys():
                    self.bom[sku] = {
                        "mpn": mpn,
                        "quantity": int(quantity * multiplier),
                        "price": price,
                        "in_stock": in_stock,
                        "available": available,
                        "board_needs": f"{project_name} ({quantity}x{multiplier})",
                    }
                else:
                    self.bom[sku]["quantity"] += int(quantity * multiplier)
                    self.bom[sku]["board_needs"] += f", {project_name} ({quantity}x{multiplier})"

    def generate_csv_bom(self, vendor):
        list_csv = [["MPN", "SKU", "Quantity", "Price [zł/unit]", "Price [zł]", "In stock", "Available", "Needed for"]]

        spare_prices, spare_n = self.get_spare_list()

        for part in self.bom.keys():
            price = 0
            try:
                spare = np.ceil(float(self.bom[part]["quantity"])*float(spare_n[np.argmax(spare_prices>float(self.bom[part]["price"]))-1]))
                price = float(self.bom[part]["price"]) * (spare + self.bom[part]["quantity"])
                #print(self.bom[part]["price"], spare, np.argmax(spare_prices>float(self.bom[part]["price"])), spare_n[np.argmax(spare_prices>float(self.bom[part]["price"]))-1])

            except ValueError:
                price = 0
                spare = np.ceil(float(self.bom[part]["quantity"])*float(spare_n[0]))

            

            list_csv.append(
                [
                    self.bom[part]["mpn"],
                    part,
                    self.bom[part]["quantity"] + spare,
                    self.bom[part]["price"],
                    price,
                    self.bom[part]["in_stock"],
                    self.bom[part]["available"],
                    self.bom[part]["board_needs"] + f' + {spare}',
                ]
            )
        with open(f"consolidated_{vendor}.csv", "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(list_csv)

    def get_file_list(self):
        if self.args.path is not None and not os.path.exists(self.args.path):
            sys.exit(termcolor.colored(f"Error: Specified filename isn't correct ({self.args.path})", "red"))
        else:
            path = self.args.path
            data = []
            with open(path, "r") as file:
                reader = csv.reader(file)
                for row in reader:
                    data.append(row)
        return data
    
    def get_spare_list(self):
        if self.args.spares is not None and not os.path.exists(self.args.spares):
            sys.exit(termcolor.colored(f"Error: Specified filename isn't correct ({self.args.spares})", "red"))
        else:
            path = self.args.spares
            prices = []
            spare_n = []
            with open(path, "r") as file:
                reader = csv.reader(file)
                for row in reader:
                    prices.append(float(row[0]))
                    spare_n.append(float(row[1]))
        print((np.array(prices), np.array(spare_n)))
        return (np.array(prices), np.array(spare_n))

    def error(self, text):
        print(termcolor.colored("Error: " + text, "red"))
        self.has_errored = True

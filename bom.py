import argparse
import os
import sys
import subprocess
import xml.etree.ElementTree as ET
from typing import Tuple
import pathlib
import csv
import copy
import colorama
import termcolor
import time
import utils

TEMPFILE_NAME = "temp.xml"
SUPPLIERS = ["Mouser", "TME"]


def mouser_generator(components, csvwriter):
    csvwriter.writerow(
        [
            "MPN",
            "SKU",
            "Quantity",
            "Price [zł/unit]",
            "Price [zł]",
            "In stock",
            "Available",
        ]
    )
    for component in components:
        print(f"Searching Mouser for {component[1]}")

        for attempts in range(30):
            response = utils.search_mouser(component[1])
            if response['Errors'] == []:
                break
            elif response['Errors'][0]['Code'] == 'TooManyRequests':
                print(termcolor.colored(f"Max requests per minute reached, waiting", "white"))
                time.sleep(2)
        part = find_matching_part(response, component[1])
        if part is not None:
            print(f"Found")
            stock = get_availability(part, int(component[2]))
            price = get_price(part, int(component[2]))
            if price is not None:
                cost = price * int(component[2])
            else:
                cost = None

            if stock is not None and stock >= int(component[2]):
                available = True
            else:
                print(termcolor.colored("Error: Not enough in stock", "red"))
                available = False

            csvwriter.writerow(
                [
                    component[0],
                    component[1],
                    component[2],
                    price,
                    cost,
                    stock,
                    available,
                ]
            )
        else:
            print(termcolor.colored("Error: Not found", "red"))


def find_matching_part(response, sku):
    return next(
        (
            part
            for part in response["SearchResults"]["Parts"]
            if "MouserPartNumber" in part
            and part["MouserPartNumber"].strip() == sku.strip()
        ),
        None,
    )


def get_availability(part, count):
    if "AvailabilityInStock" in part and part["AvailabilityInStock"] is not None:
        return int(part["AvailabilityInStock"])
    else:
        return None


def get_price(part, count):
    price_breaks = part["PriceBreaks"]
    for price in price_breaks:
        if int(price["Quantity"]) <= count:
            return float(price["Price"].split()[0].replace(",", "."))
    else:
        return None


SUPPLIER_GENERATORS = {"Mouser": mouser_generator, "TME": mouser_generator}


def add_subparser(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-a",
        "--available",
        dest="available",
        action="store_true",
        help="Run a check for part availability",
    )
    parser.add_argument(
        "-p",
        "--path",
        dest="path",
        help="Specifies path to main schematic file",
    )
    parser.add_argument(
        "-g", "--generate", dest="suppliers", choices=SUPPLIERS, nargs="+"
    )
    parser.set_defaults(func=run)


def run(args):
    BOM(args).run()


class Component:
    def __init__(
        self,
        reference: str,
        value: str,
        mpn: str | None,
        suppliers: dict[str, str | None],
    ):
        self.reference: str = reference
        self.value: str = value
        self.mpn: str | None = mpn
        self.suppliers: dict[str, str | None] = suppliers


class ComponentGroup:
    def __init__(self, suppliers: dict[str, str | None]):
        self.count: int = 1
        self.suppliers: dict[str, str | None] = suppliers

    def fill_suppliers(self, suppliers):
        for supplier in SUPPLIERS:
            if self.suppliers[supplier] is None and suppliers[supplier] is not None:
                self.suppliers[supplier] = suppliers[supplier]


class BOM:
    def __init__(self, args):
        self.args = args
        self.path = self.get_path()
        self.components: list[Component] = []
        self.grouped_components: dict[str, ComponentGroup] = {}
        self.has_errored = False

    def run(self):
        colorama.just_fix_windows_console()

        self.generate_xml_bom()
        self.parse_xml()
        self.verify_components()
        self.debunch_components()
        self.group_components()
        if self.args.suppliers is not None:
            self.generate_csv_boms()
        self.remove_temp_xml()
        if self.has_errored:
            sys.exit(termcolor.colored("There were issues found", "red"))
        else:
            print("OK!")
            sys.exit()

    def error(self, text):
        print(termcolor.colored("Error: " + text, "red"))
        self.has_errored = True

    def get_path(self):
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
            sys.exit(
                termcolor.colored(
                    f"Error: Specified filename isn't correct ({self.args.path}", "red"
                )
            )
        else:
            path = self.args.path
        return path

    def generate_xml_bom(self):
        print(f"Generating BOM using kicad-cli")
        process = subprocess.Popen(
            [
                "kicad-cli",
                "sch",
                "export",
                "python-bom",
                "-o",
                TEMPFILE_NAME,
                self.path,
            ],
            stdout=subprocess.PIPE,
        )
        process.wait()

    def parse_xml(self):
        print(f"Parsing the XML BOM")
        tree = ET.parse(TEMPFILE_NAME)
        root = tree.getroot()
        components = root.find("components")
        if components is None:
            return
        for component in components:
            ref = component.attrib["ref"]
            value_element = component.find("value")
            if value_element is not None and value_element.text is not None:
                value = value_element.text
            else:
                value = ""
            properties = component.findall("property")
            mpn = self.find_property(properties, "MPN")
            suppliers = {}
            for supplier in SUPPLIERS:
                suppliers[supplier] = self.find_property(properties, supplier)

            self.components.append(Component(ref, value, mpn, suppliers))

    def find_property(self, properties, name: str):
        for prop in properties:
            if prop.attrib["name"] == name:
                return str(prop.attrib["value"])
        return None

    def verify_components(self):
        print("Veryfing components")
        for component in self.components:
            prefix = "".join(char for char in component.reference if not char.isdigit())
            if not (prefix in ["C", "R", "TP"]):
                # Check if component has MPN
                if component.mpn is None:
                    self.error(f"Component without MPN: {component.reference}")

                # Check if component has any supplier
                if (
                    all(val is None for val in component.suppliers.values())
                    and component.mpn != "NO_MPN"
                ):
                    self.error(f"No supplier specified for: {component.reference}")

    def debunch_components(self):
        debunched_components = []
        for component in self.components:
            if component.mpn is None:
                continue
            if component.suppliers is not None: #this part handles + in MPN and SKU
                for supplier_name in component.suppliers.keys():
                    if component.suppliers[supplier_name] is not None:
                        component.mpn = "".join(component.mpn.split()) #remove whitespace
                        component.suppliers[supplier_name] = "".join(component.suppliers[supplier_name].split())
                        mpns = component.mpn.split('+')
                        skus = component.suppliers[supplier_name].split('+')
                        if len(skus) != len(mpns):
                            self.error(f'element count in SKU and MPN not equal for {component.mpn}')
                            continue
                        for i in range(len(mpns)):
                            debunched_components.append(copy.deepcopy(component))
                            debunched_components[-1].mpn = mpns[i]
                            debunched_components[-1].suppliers[supplier_name] = skus[i]
        self.components = debunched_components


    def group_components(self):
        print("Grouping components")
        for component in self.components:
            if component.mpn is None:
                continue

            if component.mpn not in self.grouped_components:
                self.grouped_components[component.mpn] = ComponentGroup(
                    component.suppliers
                )
                #print("ddd",component.suppliers)
            else:
                self.grouped_components[component.mpn].count += 1
                self.grouped_components[component.mpn].fill_suppliers(
                    component.suppliers
                )
        #for grouped_component in self.grouped_components:
            #print('X',self.grouped_components[grouped_component].suppliers)

    def generate_csv_boms(self):
        print("Generating CSV BOMS")
        pathlib.Path("bom").mkdir(parents=True, exist_ok=True)
        boms: dict[str, list[Tuple[str, str, int]]] = {"None": []}
        for supplier in self.args.suppliers:
            boms[supplier] = []

        for mpn, grouped_component in self.grouped_components.items():
            #print('lk', grouped_component.suppliers)
            if mpn != "NO_MPN":
                supplier = "None"
                for sup in self.args.suppliers:
                    if grouped_component.suppliers[sup] is not None:
                        supplier = sup
                        break

                sku = (
                    grouped_component.suppliers[supplier] if supplier != "None" else ""
                )
                if sku is not None:
                    entry = (
                        mpn,
                        sku,
                        grouped_component.count,
                    )
                    boms[supplier].append(entry)

        if len(boms["None"]) > 0:
            self.error(
                f"There were {str(len(boms['None']))} components without supplier ({[bom[0] for bom in boms['None']]})"
            )

        for supplier in self.args.suppliers:
            with open(
                (pathlib.Path("bom") / (supplier + ".csv")), "w+", newline=""
            ) as csvfile:
                csvwriter = csv.writer(csvfile, delimiter=";", quotechar='"')
                SUPPLIER_GENERATORS[supplier](boms[supplier], csvwriter)

    def remove_temp_xml(self):
        os.remove(TEMPFILE_NAME)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_subparser(parser)
    args = parser.parse_args()
    run(args)

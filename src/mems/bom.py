import argparse
import os
import sys
import subprocess
import xml.etree.ElementTree as ET
from typing import Tuple, List, Dict
import pathlib
import csv
import copy
import colorama
import termcolor
import time
from mems import utils

TEMPFILE_NAME = "temp.xml"
SUPPLIERS = ["Mouser", "TME"]


class Component:
    def __init__(
        self,
        reference: str,
        value: str | None,
        mpn: str | None,
        skus: dict[str, str],
    ):
        self.reference: str = reference
        self.value: str | None = value
        self.mpn: str | None = mpn
        self.skus: dict[str, str] = skus


class ComponentGroup:
    def __init__(self, skus: dict[str, str]):
        self.count: int = 1
        self.skus: dict[str, str] = skus


class BOMEntry:
    def __init__(self, mpn, sku, quantity):
        self.mpn = mpn
        self.sku = sku
        self.quantity = quantity


def mouser_generator(components: list[BOMEntry], csvwriter):
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
        print(f"Searching Mouser for {component.sku}")
        response = utils.search_mouser(component.sku)
        while len(response["Errors"]) > 0:
            time.sleep(2)
            response = utils.search_mouser(component.sku)

        part = mouser_find_matching_part(response, component.sku)
        if part is not None:
            print("Found")
            stock = mouser_get_availability(part)
            price = mouser_get_price(part, component.quantity)
            if price is not None:
                cost = price * int(component.quantity)
            else:
                cost = None

            if stock is not None and stock >= int(component.quantity):
                available = True
            else:
                print(termcolor.colored("Error: Not enough in stock", "red"))
                available = False

            csvwriter.writerow(
                [
                    component.mpn,
                    component.sku,
                    component.quantity,
                    price,
                    cost,
                    stock,
                    available,
                ]
            )
        else:
            print(termcolor.colored("Error: Not found", "red"))


def mouser_find_matching_part(response, sku):
    for part in response["SearchResults"]["Parts"]:
        if "MouserPartNumber" in part and part["MouserPartNumber"].strip() == sku.strip():
            return part
    return None


def mouser_get_availability(part):
    if "AvailabilityInStock" in part and part["AvailabilityInStock"] is not None:
        return int(part["AvailabilityInStock"])
    return None


def mouser_get_price(part, count):
    price_breaks = part["PriceBreaks"]
    for price in price_breaks:
        if int(price["Quantity"]) <= count:
            return float(price["Price"].split()[0].replace(",", "."))
    return None


def lab_generator(components: list[BOMEntry], csvwriter):
    csvwriter.writerow(
        [
            "Name",
            "Quantity",
        ]
    )
    for component in components:
        csvwriter.writerow(
            [
                component.mpn,
                component.quantity,
            ]
        )


SUPPLIER_GENERATORS = {
    "Mouser": mouser_generator,
    "TME": mouser_generator,
    "Lab": lab_generator,
}


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
    parser.add_argument("-g", "--generate", dest="suppliers", choices=SUPPLIERS, nargs="*")
    parser.add_argument(
        "--no-mpn",
        dest="no_mpn",
        action="store_true",
        help="Override ignoring components without mpn for bom generation",
    )
    parser.set_defaults(func=run)


def run(args):
    BOM(args).run()


class BOM:
    def __init__(self, args) -> None:
        self.args = args
        self.path = self.get_path()
        self.components: list[Component] = []
        self.grouped_components: dict[str, ComponentGroup] = {}
        self.has_errored = False

    def run(self):
        colorama.just_fix_windows_console()

        self.generate_xml_bom()
        components = self.parse_xml()
        self.verify_components(components)
        components = self.handle_multipart_components(components)
        components = self.handle_misc_components(components)
        grouped_components = self.group_components(components)

        suppliers = ["Lab"]
        if self.args.suppliers is not None:
            suppliers += self.args.suppliers
            self.generate_csv_boms(grouped_components, suppliers)

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
            sys.exit(termcolor.colored(f"Error: Specified filename isn't correct ({self.args.path}", "red"))
        else:
            path = self.args.path
        return path

    def generate_xml_bom(self):
        print("Generating BOM using kicad-cli")
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
        print("Parsing the XML BOM")
        tree = ET.parse(TEMPFILE_NAME)
        root = tree.getroot()
        components = root.find("components")
        if components is None:
            return []

        output_components = []
        for component in components:
            ref = component.attrib["ref"]
            value_element = component.find("value")
            if value_element is not None and value_element.text is not None:
                value = value_element.text
            else:
                value = None

            properties = component.findall("property")
            mpn = self.find_property(properties, "MPN")

            skus = {}
            for supplier in SUPPLIERS:
                supplier_sku = self.find_property(properties, supplier)
                if supplier_sku is not None:
                    skus[supplier] = supplier_sku

            output_components.append(Component(ref, value, mpn, skus))

        return output_components

    def find_property(self, properties, name: str):
        for prop in properties:
            if prop.attrib["name"] == name:
                return str(prop.attrib["value"])
        return None

    def verify_components(self, components: List[Component]):
        print("Veryfing components")
        for component in components:
            prefix = "".join(char for char in component.reference if not char.isdigit())
            # Check if component doen't have mpn and is not excluded from having one mandatory
            if component.mpn is None and prefix not in ["C", "R", "TP"]:
                self.error(f"Component without MPN: {component.reference}")

            # Check if component doesn't have SKU while having real MPN
            if (
                component.mpn is not None
                and component.mpn != "NO_MPN"
                and all(val is None for val in component.skus.values())
            ):
                self.error(f"No SKU specified for: {component.reference}")

    def handle_multipart_components(self, components: List[Component]) -> List[Component]:
        out_components: List[Component] = []
        for component in components:
            if component.mpn is None:
                out_components.append(component)
                continue

            mpns = component.mpn.strip().split("+")
            if len(mpns) == 1:
                out_components.append(component)
                continue

            skus: List[Tuple[str, str]] = []
            for supplier, supplier_skus in component.skus.items():
                for sku in supplier_skus.strip().split("+"):
                    skus.append((supplier, sku))

            if len(skus) != len(mpns):
                self.error(f"Element count in SKU and MPN not equal for {component.mpn}. Ignoring this component")
                continue

            for index, (supplier, sku) in enumerate(skus):
                new_component = copy.deepcopy(component)
                new_component.mpn = f"Multipart {index+1}/{len(skus)}: {mpns}"
                new_component.skus = {supplier: sku}

                out_components.append(new_component)
                print(new_component.mpn, new_component.skus)

        return out_components

    def handle_misc_components(self, components: List[Component]) -> List[Component]:
        for component in components:
            if component.mpn is None:
                prefix = "".join(char for char in component.reference if not char.isdigit())
                if component.value is not None:
                    component.mpn = prefix + component.value
                    component.skus["Lab"] = component.mpn
                else:
                    component.mpn = "MissingMPNandValue"
                    self.error("Component missing mpn and value")
        return components

    def group_components(self, components: List[Component]) -> Dict[str, ComponentGroup]:
        print("Grouping components")
        grouped_components = {}
        for component in components:
            if component.mpn is None:
                self.error("Component without MPN where all components should already have MPN's (programming bug)")
                continue

            if component.mpn not in grouped_components:
                grouped_components[component.mpn] = ComponentGroup(component.skus)
            else:
                grouped_components[component.mpn].count += 1

        return grouped_components

    def generate_csv_boms(self, grouped_components: Dict[str, ComponentGroup], suppliers: List[str]) -> None:
        print("Generating CSV BOMS")
        pathlib.Path("bom").mkdir(parents=True, exist_ok=True)

        boms: dict[str, list[BOMEntry]] = {}
        for supplier in suppliers:
            boms[supplier] = []

        no_supplier_mpns: List[str] = []

        for mpn, grouped_component in grouped_components.items():
            if mpn != "NO_MPN":
                sup: str | None = None
                for sup in suppliers:
                    if sup in grouped_component.skus and grouped_component.skus[sup] is not None:
                        supplier = sup
                        break

                if sup is not None:
                    entry = BOMEntry(
                        mpn,
                        grouped_component.skus[sup],
                        grouped_component.count,
                    )

                    boms[sup].append(entry)
                else:
                    no_supplier_mpns.append(mpn)

        if len(no_supplier_mpns) > 0:
            self.error(f"There were {str(len(no_supplier_mpns))} components without supplier ({no_supplier_mpns})")

        for supplier in suppliers:
            with open((pathlib.Path("bom") / (supplier + ".csv")), "w+", newline="") as csvfile:
                csvwriter = csv.writer(csvfile, delimiter=";", quotechar='"')
                SUPPLIER_GENERATORS[supplier](boms[supplier], csvwriter)

    def remove_temp_xml(self):
        os.remove(TEMPFILE_NAME)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_subparser(parser)
    args = parser.parse_args()
    run(args)

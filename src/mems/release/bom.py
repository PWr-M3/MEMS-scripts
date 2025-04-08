from abc import abstractmethod, ABC
import os
import sys
import subprocess
import xml.etree.ElementTree as ET
from typing import Tuple, List, Dict
import pathlib
import csv
import copy
import time
from mems import utils
import logging


logger = logging.getLogger(__name__)


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

    def __repr__(self):
        return f"{self.quantity} pcs MPN: {self.mpn} SKU: {self.sku}"


SUPPLIERS = {}


class Supplier(ABC):
    def __init_subclass__(cls, /, name, **kwargs):
        super().__init_subclass__(**kwargs)
        SUPPLIERS[name] = cls
        cls.name = name

    def __init__(self):
        self.components: list[BOMEntry] = list()

    def add_components(self, components: BOMEntry):
        self.components.append(components)

    @abstractmethod
    def write_csv(self, csvwriter):
        return


class MouserSupplier(Supplier, name="Mouser"):
    def write_csv(self, csvwriter):
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
        for component in self.components:
            logger.info(f"Searching Mouser for {component.sku}")
            response = utils.search_mouser(component.sku)
            while len(response["Errors"]) > 0:
                time.sleep(2)
                response = utils.search_mouser(component.sku)

            part = self.find_matching_part(response, component.sku)
            if part is not None:
                logger.info("Found")
                stock = self.get_availability(part)
                price = self.mouser_get_price(part, component.quantity)
                if price is not None:
                    cost = price * int(component.quantity)
                else:
                    cost = None

                if stock is not None and stock >= int(component.quantity):
                    available = True
                else:
                    logger.error("Not enough in stock")
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
                logger.error("Not found")

    @staticmethod
    def find_matching_part(response, sku):
        for part in response["SearchResults"]["Parts"]:
            if "MouserPartNumber" in part and part["MouserPartNumber"].strip() == sku.strip():
                return part
        return None

    @staticmethod
    def get_availability(part):
        if "AvailabilityInStock" in part and part["AvailabilityInStock"] is not None:
            return int(part["AvailabilityInStock"])
        return None

    @staticmethod
    def mouser_get_price(part, count):
        price_breaks = part["PriceBreaks"]
        for price in price_breaks:
            if int(price["Quantity"]) <= count:
                return float(price["Price"].split()[0].replace(",", "."))
        return None


class LabSupplier(Supplier, name="Lab"):
    def write_csv(self, csvwriter):
        csvwriter.writerow(
            [
                "Name",
                "Quantity",
            ]
        )
        for component in self.components:
            csvwriter.writerow(
                [
                    component.mpn,
                    component.quantity,
                ]
            )


class TMESupplier(Supplier, name="TME"):
    def write_csv(self, csvwriter):

        for component in self.components:
            csvwriter.writerow(
                [
                    component.sku,
                    component.quantity,
                ]
            )


class LCSCSupplier(Supplier, name="LCSC"):
    def write_csv(self, csvwriter):
        csvwriter.writerow(
            [
                "MPN",
                "SKU",
                "Quantity",
                "Price [USD/unit]",
                "Price [USD]",
                "In stock",
                "Available",
            ]
        )
        for component in self.components:
            logger.info(f"Searching LCSC for {component.sku}")
            part = utils.search_lcsc(component.sku)
            if part is None:
                logger.error("Not found")
                continue

            logger.info("Found")
            price = part.get_price(component.quantity)
            cost = price * component.quantity
            available = part.in_stock_qty >= component.quantity
            if not available:
                logger.error("Not enough in stock")

            csvwriter.writerow(
                [
                    component.mpn,
                    component.sku,
                    component.quantity,
                    price,
                    cost,
                    part.in_stock_qty,
                    available,
                ]
            )



def add_subparser(subparsers):
    parser = subparsers.add_parser("bom", help="Generate BOM and execute BOM checks")
    parser.set_defaults(func=run)


def run(_ = None):
    BOM().run()

def get_filename():
    filename = utils.get_pro_filename()
    if filename is None:
        logger.error("No project file found")
        sys.exit(0)
    filename = filename.parent / "fab" / "bom" / "temp.xml"
    return str(filename)


class BOM:
    def __init__(self) -> None:
        self.path = utils.get_main_sch_filename()
        self.components: list[Component] = []
        self.grouped_components: dict[str, ComponentGroup] = {}
        self.has_errored = False

    def run(self):
        self.generate_xml_bom()
        components = self.parse_xml()
        self.verify_components(components)
        components = self.handle_multipart_components(components)
        components = self.handle_misc_components(components)
        grouped_components = self.group_components(components)

        suppliers = ["Mouser", "TME", "LCSC"]
        self.generate_csv_boms(grouped_components, suppliers)

        self.remove_temp_xml()
        if self.has_errored:
            logger.error("There were issues found")
        else:
            logger.info("OK!")


    def error(self, text):
        logger.error(text)
        self.has_errored = True

    def generate_xml_bom(self):
        logger.info(f"Generating BOM using kicad-cli from {self.path}")
        process = subprocess.Popen(
            [
                "kicad-cli",
                "sch",
                "export",
                "python-bom",
                "-o",
                get_filename(),
                str(self.path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        process.wait()

    def parse_xml(self):
        logger.info("Parsing the XML BOM")
        tree = ET.parse(get_filename())
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
        logger.info("Veryfing components")
        for component in components:
            prefix = "".join(char for char in component.reference if not char.isdigit())
            # Check if component doesn't have mpn and is not excluded from having one mandatory
            if component.mpn is None and prefix not in ["TP", "H"]:
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
                    skus.append((supplier, sku.strip()))

            if len(skus) != len(mpns):
                self.error(f"Element count in SKU and MPN not equal for {component.mpn}. Ignoring this component")
                continue

            for index, (supplier, sku) in enumerate(skus):
                new_component = copy.deepcopy(component)
                new_component.mpn = f"{sku} from Multipart: {mpns}"
                new_component.skus = {supplier: sku}

                out_components.append(new_component)

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
        logger.info("Grouping components")
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
        logger.info("Generating CSV BOMS")
        pathlib.Path("bom").mkdir(parents=True, exist_ok=True)

        boms: Dict[str, Supplier] = {name: SUPPLIERS[name]() for name in suppliers}
        no_supplier_mpns: List[str] = []

        for mpn, grouped_component in grouped_components.items():
            if mpn != "NO_MPN":
                supplier: str | None = None
                for sup in suppliers:
                    if sup in grouped_component.skus and grouped_component.skus[sup] is not None:
                        supplier = sup
                        break

                if supplier is not None:
                    entry = BOMEntry(
                        mpn,
                        grouped_component.skus[supplier],
                        grouped_component.count,
                    )

                    boms[supplier].add_components(entry)
                else:
                    no_supplier_mpns.append(mpn)

        if len(no_supplier_mpns) > 0:
            self.error(f"There were {str(len(no_supplier_mpns))} components without supplier ({no_supplier_mpns})")

        project_filename = utils.get_pro_filename()
        if project_filename is None:
            logger.error("No project file found")
            sys.exit(1)
        path = project_filename.parent / "fab" / "bom"
        path.mkdir(parents=True, exist_ok=True)
        for name, bom in boms.items():
            with open((path / (name + ".csv")), "w+", newline="") as csvfile:
                csvwriter = csv.writer(csvfile, delimiter=";", quotechar='"')
                bom.write_csv(csvwriter)

    def remove_temp_xml(self):
        os.remove(get_filename())

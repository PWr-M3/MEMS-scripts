import argparse
import logging
import sys
import time
from typing import Callable, cast
from dataclasses import dataclass
from abc import ABC, abstractmethod
import itertools
import math

import kiutils.symbol
import kiutils.utils.sexpr
from mems.library.lib_utils import load_symbol_library, get_lib_repo, check_repo_clean, commit_lib_repo


import mems.utils as utils

logger = logging.getLogger(__name__)


@dataclass
class CapacitorParamsOptional:
    package: str | None = None
    capacitance_pf: int | None = None
    dielectric: str | None = None
    tolerance_ppm: int | None = None
    voltage_mv: float | None = None


@dataclass
class CapacitorParams:
    package: str
    capacitance_pf: int
    dielectric: str
    tolerance_ppm: int
    voltage_mv: int


class CapacitorSeries(ABC):
    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        return ""

    @classmethod
    @abstractmethod
    def get_packages(cls, params: CapacitorParamsOptional) -> list[str]:
        return []

    @classmethod
    @abstractmethod
    def get_capacitances(cls, params: CapacitorParamsOptional) -> list[int]:
        return []

    @classmethod
    @abstractmethod
    def get_dielectrics(cls, params: CapacitorParamsOptional) -> list[str]:
        return []

    @classmethod
    @abstractmethod
    def get_tolerances(cls, params: CapacitorParamsOptional) -> list[int]:
        return []

    @classmethod
    @abstractmethod
    def get_voltages(cls, params: CapacitorParamsOptional) -> list[int]:
        return []

    @classmethod
    def supports(cls, params: CapacitorParamsOptional) -> bool:
        if params.package is not None and params.package not in cls.get_packages(params):
            return False
        if params.capacitance_pf is not None and params.capacitance_pf not in cls.get_capacitances(params):
            return False
        if params.dielectric is not None and params.dielectric not in cls.get_dielectrics(params):
            return False
        if params.tolerance_ppm is not None and params.tolerance_ppm not in cls.get_tolerances(params):
            return False
        if params.voltage_mv is not None and params.voltage_mv not in cls.get_voltages(params):
            return False
        return True

    @classmethod
    def get_on_mouser(cls, params: CapacitorParams) -> tuple[str, str] | None:
        if not cls.supports(cast(CapacitorParamsOptional, params)):
            return None
        mpn = cls.get_mpn(params)

        logger.info(f"Searching mouser for part number {mpn} to see if it exists")
        response = utils.search_mouser(mpn)
        while len(response["Errors"]) > 0:
            logger.warn(f"Mouser error. {response['Errors'][0]}. Trying again")
            time.sleep(2)
            response = utils.search_mouser(mpn)

        parts = []
        for part in response["SearchResults"]["Parts"]:
            p_mpn = part.get("ManufacturerPartNumber", None)
            sku = part.get("MouserPartNumber", None)
            availibility = part.get("Availability", None)
            price_breaks = part.get("PriceBreaks", [])
            if (
                price_breaks is None
                or len(price_breaks) == 0
                or not any(price["Quantity"] <= 10 for price in price_breaks)
            ):
                availibility = False
            price = None
            if len(price_breaks) > 0:
                price = float(price_breaks[0]["Price"].replace(",", ".").split()[0])
            parts.append((p_mpn, sku, availibility, price))

        filters = [
            lambda x: x[2] is not None and x[2] != "None" and x[2],
            lambda x: mpn in x[0],
            lambda x: x[1] is not None and x[1] != "None" and x[1] != "N/A",
        ]
        parts_filtered = filter(lambda x: all(f(x) for f in filters), parts)
        parts_sorted = sorted(parts_filtered, key=lambda part: part[3])

        if not parts_sorted:
            return None
        part = parts_sorted[0]

        logger.info(f"Found part: {part[0]} for {part[3]} zł")

        return (part[0], part[1])

    @classmethod
    @abstractmethod
    def get_mpn(cls, params: CapacitorParams) -> str:
        return "NON_EXISTANT_CAPACITOR_MPN"

    @classmethod
    @abstractmethod
    def get_template_name(cls, params: CapacitorParams) -> str:
        return "NON_EXISTANT_TEMPLATE"

    @classmethod
    @abstractmethod
    def get_datasheet(cls, mpn: str) -> str:
        return "NON_EXISTANT_DATASHEET"


class KemetC0G(CapacitorSeries):
    @classmethod
    def get_name(cls):
        return "KemetC0G"

    @classmethod
    def get_tolerances(cls, params):
        _ = params
        return [10_000, 20_000, 50_000, 100_000, 200_000]

    @classmethod
    def get_packages(cls, params):
        _ = params
        return ["0402", "0805"]

    @classmethod
    def get_dielectrics(cls, params):
        _ = params
        return ["C0G"]

    @classmethod
    def get_voltages(cls, params):
        _ = params
        return [10_000, 16_000, 25_000, 50_000, 100_000, 200_000, 250_000]

    @classmethod
    def get_capacitances(cls, params):
        _ = params
        prefixes = [
            1,
            1.1,
            1.2,
            1.3,
            1.5,
            1.6,
            1.8,
            2,
            2.2,
            2.4,
            2.7,
            3.0,
            3.3,
            3.6,
            3.9,
            4.3,
            4.7,
            5.1,
            5.6,
            6.2,
            6.8,
            7.5,
            8.2,
            9.1,
        ]
        multipliers = [1e-12, 1e-11, 1e-10, 1e-9, 1e-8]
        return [int(p * m * 1e12) for m, p in itertools.product(multipliers, prefixes)]

    @classmethod
    def get_mpn(cls, params):
        value = params.capacitance_pf
        order = math.floor(math.log10(value)) - 1
        prefix = math.floor(value / math.pow(10, order))
        if order == -1:
            order = 9
        tolerances = {10_000: "F", 20_000: "G", 50_000: "J", 100_000: "K", 200_000: "M"}
        voltages = {10_000: 8, 16_000: 4, 25_000: 3, 50_000: 5, 100_000: 1, 200_000: 2, 250_000: "A"}

        return f"C{params.package}C{prefix:2d}{order:1d}{tolerances[params.tolerance_ppm]}{voltages[int(params.voltage_mv)]}G"

    @classmethod
    def get_template_name(cls, params):
        _ = params
        return "C"

    @classmethod
    def get_datasheet(cls, mpn):
        return f"https://ksim3.kemet.com/capacitor-simulation?pn={mpn}"


class KemetX7R(CapacitorSeries):
    @classmethod
    def get_name(cls):
        return "KemetX7R"

    @classmethod
    def get_tolerances(cls, params):
        _ = params
        return [50_000, 100_000, 200_000]

    @classmethod
    def get_packages(cls, params):
        _ = params
        return ["0402", "0805"]

    @classmethod
    def get_dielectrics(cls, params):
        _ = params
        return ["X7R"]

    @classmethod
    def get_voltages(cls, params):
        _ = params
        return [6_300, 10_000, 16_000, 25_000, 35_000, 50_000, 100_000, 200_000, 250_000]

    @classmethod
    def get_capacitances(cls, params):
        _ = params
        prefixes = [
            1,
            1.2,
            1.5,
            1.8,
            2.2,
            2.7,
            3.3,
            3.9,
            4.7,
            5.6,
            6.8,
            8.2,
        ]
        multipliers = [1e-11, 1e-10, 1e-9, 1e-8, 1e-7, 1e-6]
        result = [int(p * m * 1e12) for m, p in itertools.product(multipliers, prefixes)]
        result += [int(10e-6 * 1e12), int(22e-6 * 1e12)]
        return result

    @classmethod
    def get_mpn(cls, params):
        value = params.capacitance_pf
        order = math.floor(math.log10(value)) - 1
        prefix = math.floor(value / math.pow(10, order))
        if order == -1:
            order = 9
        tolerances = {50_000: "J", 100_000: "K", 200_000: "M"}
        voltages = {
            6_300: 9,
            10_000: 8,
            16_000: 4,
            25_000: 3,
            35_000: 6,
            50_000: 5,
            100_000: 1,
            200_000: 2,
            250_000: "A",
        }

        return (
            f"C{params.package}C{prefix}{order:1d}{tolerances[params.tolerance_ppm]}{voltages[int(params.voltage_mv)]}R"
        )

    @classmethod
    def get_template_name(cls, params):
        _ = params
        return "C"

    @classmethod
    def get_datasheet(cls, mpn):
        return f"https://ksim3.kemet.com/capacitor-simulation?pn={mpn}"


class KemetX5R(CapacitorSeries):
    @classmethod
    def get_name(cls):
        return "KemetX5R"

    @classmethod
    def get_tolerances(cls, params):
        _ = params
        return [100_000, 200_000]

    @classmethod
    def get_packages(cls, params):
        _ = params
        return ["0402", "0805"]

    @classmethod
    def get_dielectrics(cls, params):
        _ = params
        return ["X5R"]

    @classmethod
    def get_voltages(cls, params):
        _ = params
        return [4_000, 6_300, 10_000, 16_000, 25_000, 35_000, 50_000]

    @classmethod
    def get_capacitances(cls, params):
        _ = params
        prefixes = [
            1,
            1.2,
            1.5,
            1.8,
            2.2,
            2.7,
            3.3,
            3.9,
            4.7,
            5.6,
            6.8,
            8.2,
        ]
        multipliers = [1e-8, 1e-7, 1e-6]
        result = [int(p * m * 1e12) for m, p in itertools.product(multipliers, prefixes)]
        result += [int(10e-6 * 1e12), int(22e-6 * 1e12), int(47e-6 * 1e12)]
        return result

    @classmethod
    def get_mpn(cls, params):
        value = params.capacitance_pf
        order = math.floor(math.log10(value)) - 1
        prefix = math.floor(value / math.pow(10, order))
        if order == -1:
            order = 9
        tolerances = {100_000: "K", 200_000: "M"}
        voltages = {
            4_000: 7,
            6_300: 9,
            10_000: 8,
            16_000: 4,
            25_000: 3,
            35_000: 6,
            50_000: 5,
        }

        return (
            f"C{params.package}C{prefix}{order:1d}{tolerances[params.tolerance_ppm]}{voltages[int(params.voltage_mv)]}P"
        )

    @classmethod
    def get_template_name(cls, params):
        _ = params
        return "C"

    @classmethod
    def get_datasheet(cls, mpn):
        return f"https://ksim3.kemet.com/capacitor-simulation?pn={mpn}"


SERIES: list[type[CapacitorSeries]] = [KemetC0G, KemetX7R, KemetX5R]

PACKAGES = {"0805": "Capacitor_SMD:C_0805_2012Metric", "0402": "Capacitor_SMD:C_0402_1005Metric"}


def add_subparser(parser: argparse.ArgumentParser):
    parser.add_argument("-p", "--package", dest="package", type=str)
    parser.add_argument("-c", "--capacitance", dest="capacitance", type=str)
    parser.add_argument("-d", "--dielectric", dest="dielectric", type=str)
    parser.add_argument("-t", "--tolerance", dest="tolerance", type=float)
    parser.add_argument("-v", "--voltage", dest="voltage", type=str)
    parser.add_argument("-i", "--index", dest="index", type=int)
    parser.add_argument("--dry", "--dry-run", dest="dry", action="store_true")


def print_options(params: CapacitorParamsOptional, f: Callable[[type[CapacitorSeries]], list[str]]) -> None:
    for series in SERIES:
        if series.supports(params):
            print(f"{series.get_name()}:")
            for value in f(series):
                print(value)


engineering_prefixes = {
    "T": 12,
    "G": 9,
    "M": 6,
    "k": 3,
    "m": -3,
    "u": -6,
    "n": -9,
    "p": -12,
    "f": -15,
    "a": -18,
}


def parse_engineering(parsed: str) -> float:
    parsed = parsed.strip()
    multiplier = 1.0
    for prefix, exponent in engineering_prefixes.items():
        if prefix in parsed:
            multiplier = math.pow(10, exponent)
            parsed = parsed.replace(prefix, ".")
    value = float(parsed)
    return value * multiplier


def format_engineering(value: float, decimal_count: int = 2, as_separator: bool = False) -> str:
    exponent = math.floor(math.log10(value))
    complete = math.floor(exponent // 3 * 3)
    remainder = exponent % 3
    if complete == 0:
        prefix = ""
    else:
        prefix, _ = next(filter(lambda t: t[1] == complete, engineering_prefixes.items()))
    number = round(value * math.pow(10, remainder - exponent), decimal_count)
    if (number - math.floor(number)) > 1e-20:
        if as_separator:
            return f"{number}".replace(".", prefix).replace(",", prefix)  # Ugly solution
        return f"{number}{prefix}"
    return f"{int(number)}{prefix}"


def create(args: argparse.Namespace) -> None:
    repo = get_lib_repo()
    check_repo_clean(repo)

    params = CapacitorParamsOptional(
        args.package,
        int(parse_engineering(args.capacitance) * 1e12) if args.capacitance is not None else None,
        args.dielectric,
        int(args.tolerance * 1e4) if args.tolerance is not None else None,
        int(parse_engineering(args.voltage) * 1e3) if args.voltage is not None else None,
    )
    acquire_parameters(params)

    series = select_series(args.index, params)

    params_full = cast(CapacitorParams, params)
    ret = series.get_on_mouser(params_full)
    if ret is not None:
        mpn, sku = ret
        logger.info("Capacitor exists. Creating new symbol.")
        if not args.dry:
            add_symbol(params_full, series, mpn, sku)
            commit_lib_repo(repo, f"Add {mpn} capacitor")
    else:
        logger.error(f"MPN: {series.get_mpn(params_full)} doesn't exist.")
        sys.exit(1)


def add_symbol(params: CapacitorParams, series: type[CapacitorSeries], mpn: str, sku: str):
    library = load_symbol_library("MEMS_Capacitors")
    name = series.get_template_name(params)

    description = (
        f"{format_engineering(params.capacitance_pf*1e-12)}F capacitor"
        f", {series.get_name()} series"
        f", tolerance {int(params.tolerance_ppm*1e-4)}%"
        f", {int(params.voltage_mv*1e-3)}V"
    )
    name = (
        f"C"
        f"_{format_engineering(params.capacitance_pf*1e-12, as_separator=True)}"
        f"_{params.package}"
        f"_{int(params.voltage_mv*1e-3)}V"
        f"_{params.dielectric}"
        f"_{mpn}"
    )

    replacements = {
        "TEMPLATE_NAME": name,
        "TEMPLATE_VALUE": format_engineering(params.capacitance_pf * 1e-12, as_separator=True),
        "TEMPLATE_MPN": mpn,
        "TEMPLATE_MOUSER": sku,
        "TEMPLATE_DIELECTRIC": params.dielectric,
        "TEMPLATE_TOLERANCE": f"{params.tolerance_ppm*1e-4:.1f}%",
        "TEMPLATE_VOLTAGE": f"{params.voltage_mv*1e-3:.1f}V",
        "TEMPLATE_DESCRIPTION": description,
        "TEMPLATE_DATASHEET": series.get_datasheet(mpn),
        "TEMPLATE_FOOTPRINT": PACKAGES[params.package],
        "TEMPLATE_TEMPLATE": series.get_template_name(params),
    }
    sexpr = TEMPLATE
    for old, new in replacements.items():
        sexpr = sexpr.replace(old, new)

    new_symbol = kiutils.symbol.Symbol.from_sexpr(kiutils.utils.sexpr.parse_sexp(sexpr))
    logger.info(f"New symbol created. MPN: {mpn}")
    library.symbols.append(new_symbol)
    library.to_file()
    logger.info("Symbol added to library and saved")


def acquire_parameters(params: CapacitorParamsOptional) -> None:
    if params.package is None:
        print("Package not specified, pass it with '-p', supported values are:")
        print_options(params, lambda s: s.get_packages(params))
        sys.exit(0)
    if params.dielectric is None:
        print("Dielectric not specified, pass it with '-d', supported values are:")
        print_options(params, lambda s: s.get_dielectrics(params))
        sys.exit(0)
    if params.voltage_mv is None:
        print("Voltage not specified, pass it with '-v', supported values are:")
        print_options(params, lambda s: [format_engineering(volt * 1e-3) + "V" for volt in s.get_voltages(params)])
        sys.exit(0)
    if params.tolerance_ppm is None:
        print("Tolerance not specified, pass it with '-t' supported values are:")
        print_options(params, lambda s: [str(tol * 1e-4) + "%" for tol in s.get_tolerances(params)])
        sys.exit(0)
    if params.capacitance_pf is None:
        print("Capacitance not specified, pass it with '-c', supported values are:")
        print_options(params, lambda s: [format_engineering(cap * 1e-12) + "F" for cap in s.get_capacitances(params)])
        sys.exit(0)


def select_series(index: int | None, params: CapacitorParamsOptional) -> type[CapacitorSeries]:
    params_full = cast(CapacitorParams, params)
    supporting_series = [series for series in SERIES if series.supports(params)]
    if index is None and len(supporting_series) > 1:
        print("Multiple series suppport passed parameter combination. Pass index with '-i' to select one:")
        for series in supporting_series:
            print(f"{series.get_name()}: {series.get_mpn(params_full)}")
        sys.exit(0)
    if not supporting_series:
        print("No series supports passed parameter combination.")
        sys.exit(1)
    if index is not None:
        if index >= len(supporting_series):
            print(f"Passed index: {index} is incorrect. There are only {len(supporting_series)} possible choices")
            sys.exit(1)
        return supporting_series[index]

    return supporting_series[0]


TEMPLATE = """
(symbol "TEMPLATE_NAME"
		(extends "C")
		(property "Reference" "C"
			(at 0.254 1.778 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(justify left)
			)
		)
		(property "Value" "TEMPLATE_VALUE"
			(at 0.254 -2.032 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(justify left)
			)
		)
		(property "Footprint" "TEMPLATE_FOOTPRINT"
			(at 0 -25.4 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "Datasheet" "TEMPLATE_DATASHEET"
			(at 0 -10.16 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "Description" "TEMPLATE_DESCRIPTION"
			(at 0 -27.94 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "MPN" "TEMPLATE_MPN"
			(at 0 -17.78 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "Mouser" "TEMPLATE_MOUSER"
			(at 0 -22.86 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "Dielectric" "TEMPLATE_DIELECTRIC"
			(at 0 -15.24 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "Tolerance" "TEMPLATE_TOLERANCE"
			(at 0 -12.7 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "Voltage" "TEMPLATE_VOLTAGE"
			(at 0 -20.32 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "ki_keywords" "capacitor cap"
			(at 0 0 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "ki_fp_filters" "C_*"
			(at 0 0 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
	)
"""

import argparse
import logging
import sys
import time
from typing import Callable, cast
from dataclasses import dataclass
from abc import ABC, abstractmethod
import itertools
import math


import mems.utils as utils

logger = logging.getLogger(__name__)


@dataclass
class CapacitorParamsOptional:
    package: str | None = None
    capacitance: float | None = None
    dielectric: str | None = None
    tolerance: float | None = None
    voltage: float | None = None


@dataclass
class CapacitorParams:
    package: str
    capacitance: float
    dielectric: str
    tolerance: float
    voltage: float


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
    def get_capacitances(cls, params: CapacitorParamsOptional) -> list[float]:
        return []

    @classmethod
    @abstractmethod
    def get_dielectrics(cls, params: CapacitorParamsOptional) -> list[str]:
        return []

    @classmethod
    @abstractmethod
    def get_tolerances(cls, params: CapacitorParamsOptional) -> list[float]:
        return []

    @classmethod
    @abstractmethod
    def get_voltages(cls, params: CapacitorParamsOptional) -> list[float]:
        return []

    @classmethod
    def supports(cls, params: CapacitorParamsOptional) -> bool:
        if params.package is not None and params.package not in cls.get_packages(params):
            return False
        if params.capacitance is not None and params.capacitance not in cls.get_capacitances(params):
            return False
        if params.dielectric is not None and params.dielectric not in cls.get_dielectrics(params):
            return False
        if params.tolerance is not None and params.tolerance not in cls.get_tolerances(params):
            return False
        if params.voltage is not None and params.voltage not in cls.get_voltages(params):
            return False
        return True

    @classmethod
    def exists(cls, params: CapacitorParams) -> bool:
        if not cls.supports(cast(CapacitorParamsOptional, params)):
            return False
        mpn = cls.get_mpn(params)

        logger.info(f"Searching mouser for part number {mpn} to see if it exists")
        response = utils.search_mouser(mpn)
        while len(response["Errors"]) > 0:
            logger.warn(f"Mouser error. {response['Errors'][0]}. Trying again")
            time.sleep(2)
            response = utils.search_mouser(mpn)

        print(response)

        for part in response["SearchResults"]["Parts"]:
            if "ManufacturerPartNumber" in part and part["ManufacturerPartNumber"].strip() == mpn:
                return True

        return False

    @classmethod
    @abstractmethod
    def get_mpn(cls, params: CapacitorParams) -> str:
        return "NON_EXISTANT_CAPACITOR_MPN"


class KemetC0G(CapacitorSeries):
    @classmethod
    def get_name(cls):
        return "KemetC0G"

    @classmethod
    def get_tolerances(cls, params):
        _ = params
        return [0.01, 0.02, 0.05, 0.1, 0.2]

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
        return [10.0, 16.0, 25.0, 50.0, 100.0, 200.0, 250.0]

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
        return [p * m for m, p in itertools.product(multipliers, prefixes)]

    @classmethod
    def get_mpn(cls, params):
        value = params.capacitance / 1e-12
        order = math.floor(math.log10(value))
        prefix = math.floor(value / math.pow(10, order - 1))
        if order == 0:
            order = 9
        tolerances = {0.01: "F", 0.02: "G", 0.05: "J", 0.1: "K", 0.2: "M"}
        voltages = {10: 8, 16: 4, 25: 3, 50: 5, 100: 1, 200: 2, 250: "A"}

        return (
            f"C{params.package}C{prefix:2d}{order:1d}{tolerances[params.tolerance]}{voltages[int(params.voltage)]}GAC"
        )


SERIES: list[type[CapacitorSeries]] = [KemetC0G]


def add_subparser(parser: argparse.ArgumentParser):
    parser.add_argument("-p", "--package", dest="package", type=str)
    parser.add_argument("-c", "--capacitance", dest="capacitance", type=float)
    parser.add_argument("-d", "--dielectric", dest="dielectric", type=str)
    parser.add_argument("-t", "--tolerance", dest="tolerance", type=float)
    parser.add_argument("-v", "--voltage", dest="voltage", type=float)


def print_options(
    f: Callable[[type[CapacitorSeries]], list[str]] | Callable[[type[CapacitorSeries]], list[float]],
    params: CapacitorParamsOptional,
) -> None:
    for series in SERIES:
        if series.supports(params):
            print(f"{series.get_name()}:")
            for value in f(series):
                print(f"\t{value}")


def create(args: argparse.Namespace) -> None:
    params = CapacitorParamsOptional(args.package, args.capacitance, args.dielectric, args.tolerance, args.voltage)
    if params.package is None:
        print("Package not specified, supported values are:")
        print_options(lambda s: s.get_packages(params), params)
        sys.exit(0)
    if params.dielectric is None:
        print("Dielectric not specified, supported values are:")
        print_options(lambda s: s.get_dielectrics(params), params)
        sys.exit(0)
    if params.voltage is None:
        print("Voltage not specified, supported values are:")
        print_options(lambda s: s.get_voltages(params), params)
        sys.exit(0)
    if params.tolerance is None:
        print("Tolerance not specified, supported values are:")
        print_options(lambda s: s.get_tolerances(params), params)
        sys.exit(0)
    if params.capacitance is None:
        print("Capacitance not specified, supported values are:")
        print_options(lambda s: s.get_capacitances(params), params)
        sys.exit(0)
    params_full = cast(CapacitorParams, params)
    for series in SERIES:
        if series.supports(params):
            print(series.get_mpn(params_full))

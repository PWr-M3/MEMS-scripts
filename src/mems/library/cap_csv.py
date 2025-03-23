import logging
import sys
import csv

import kiutils.symbol
import kiutils.utils

from mems.library.lib_utils import get_lib_path, get_lib_repo, load_symbol_library
from mems.utils import check_repo_clean
from mems.engineering import format_engineering

logger = logging.getLogger(__name__)

CAPACITOR_LIB_NAME = "MEMS_Capacitors-Generated"
POLARIZED_CAP_TYPES = ["Aluminum", "Tantalum"]

def regenerate():
    repo = get_lib_repo()
    check_repo_clean(repo)
    library = load_symbol_library(CAPACITOR_LIB_NAME) 
    csv = load_csv()
    capacitors = []
    for row in csv:
        capacitors.append(create_capacitor_from_row(row))

    to_remove = []
    for symbol in library.symbols:
        if symbol.entryName not in ["C", "C_Pol"]:
            to_remove.append(symbol)
    for symbol in to_remove:
        library.symbols.remove(symbol)
    for symbol in capacitors:
        library.symbols.append(symbol)
    library.to_file()

def load_csv() -> list[dict]:
    path = get_lib_path()
    if path is None:
        logger.error("Library is not installed. Install with 'mems library install <path>'")
        sys.exit(1)
    path = (path / "symbols" / CAPACITOR_LIB_NAME).with_suffix(".csv")
    if not path.exists():
        logger.error("No csv file found.")
        sys.exit(1)
    rows = []
    with open(path) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rows.append(row)
    return sorted(rows, key=lambda row: float(row["Value scientific [F]:"]))

def create_capacitor_from_row(row: dict) -> kiutils.symbol.Symbol:
    template_name = "C"
    polarized = False
    if row["Type:"] in POLARIZED_CAP_TYPES:
        template_name = "C_Pol"
        polarized = True

    description = (
        f"{format_engineering(float(row['Value scientific [F]:']))}F capacitor"
        f", {row['Tolerance:']}"
        f", {row['Voltage [V]:']}V"
        f", {row['Type:']}"
        f", {row['Package:']}"
    )
    name = (
        f"{"C_Pol" if polarized else "C"}"
        f"_{format_engineering(float(row['Value scientific [F]:']), as_separator=True)}"
        f"_{row['Package:']}"
        f"_{row['Voltage [V]:']}V"
        f"_{row['Type:']}"
        f"_{row['MPN:']}"
    )

    replacements = {
        "TEMPLATE_NAME": name,
        "TEMPLATE_VALUE": format_engineering(float(row['Value scientific [F]:']), as_separator=True),
        "TEMPLATE_MPN": row["MPN:"],
        "TEMPLATE_MOUSER": row["Mouser:"],
        "TEMPLATE_TYPE": row["Type:"],
        "TEMPLATE_TOLERANCE": row["Tolerance:"],
        "TEMPLATE_VOLTAGE": f"{row['Voltage [V]:']}V",
        "TEMPLATE_DESCRIPTION": description,
        "TEMPLATE_DATASHEET": row["Datasheet:"],
        "TEMPLATE_FOOTPRINT": row["Footprint:"],
        "TEMPLATE_TEMPLATE": template_name,
    }
    sexpr = TEMPLATE
    for old, new in replacements.items():
        sexpr = sexpr.replace(old, new)

    new_symbol = kiutils.symbol.Symbol.from_sexpr(kiutils.utils.sexpr.parse_sexp(sexpr))
    logger.info(f"New symbol created. MPN: {row['MPN:']}")
    return new_symbol




TEMPLATE = """
(symbol "TEMPLATE_NAME"
		(extends "TEMPLATE_TEMPLATE")
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
		(property "Type" "TEMPLATE_TYPE"
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

import logging
import sys
import csv

import kiutils.symbol
import kiutils.utils

from mems.library.lib_utils import check_repo_clean, get_lib_path, get_lib_repo, load_symbol_library
from mems.utils import format_engineering

logger = logging.getLogger(__name__)

RESISTOR_LIB_NAME = "MEMS_Resistors-Generated"

def regenerate():
    repo = get_lib_repo()
    check_repo_clean(repo)
    library = load_symbol_library(RESISTOR_LIB_NAME) 
    csv = load_csv()
    resistors = []
    for row in csv:
        resistors.append(create_resistor_from_row(row))

    to_remove = []
    for symbol in library.symbols:
        if symbol.entryName not in ["R"]:
            to_remove.append(symbol)
    for symbol in to_remove:
        library.symbols.remove(symbol)
    for symbol in resistors:
        library.symbols.append(symbol)
    library.to_file()

def load_csv() -> list[dict]:
    path = get_lib_path()
    if path is None:
        logger.error("Library is not installed. Install with 'mems library install <path>'")
        sys.exit(1)
    path = (path / "symbols" / RESISTOR_LIB_NAME).with_suffix(".csv")
    if not path.exists():
        logger.error("No csv file found.")
        sys.exit(1)
    rows = []
    with open(path) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rows.append(row)
    return sorted(rows, key=lambda row: float(row["Value scientific [Ohm]:"]))

def create_resistor_from_row(row: dict) -> kiutils.symbol.Symbol:
    template_name = "R"

    description = (
        f"{format_engineering(float(row['Value scientific [Ohm]:']))}Ω capacitor"
        f", {float(row['Tolerance [%]:'])}%"
        f", {float(row['Power [W]:'])*1000}mW"
        f", {str(row['TempCo [ppm]:'])+"ppm" if row['TempCo [ppm]:'] else ''}"
        f", {row['Type:']}"
        f", {row['Package:']}"
    )
    name = (
        f"R"
        f"_{format_engineering(float(row['Value scientific [Ohm]:']), as_separator=True, unit="R")}"
        f"_{row['Package:']}"
        f"_{float(row['Tolerance [%]:']):g}%"
        f"{'_' + str(row['TempCo [ppm]:'])+"ppm" if row['TempCo [ppm]:'] else ''}"
        f"_{row['MPN:']}"
    )

    replacements = {
        "TEMPLATE_NAME": name,
        "TEMPLATE_VALUE": format_engineering(float(row['Value scientific [Ohm]:']), as_separator=True, unit="R"),
        "TEMPLATE_MPN": row["MPN:"],
        "TEMPLATE_MOUSER": row["Mouser:"],
        "TEMPLATE_TME": row["TME:"],
        "TEMPLATE_LCSC": row["LCSC:"],
        "TEMPLATE_TOLERANCE": f"{float(row['Tolerance [%]:'])}%",
        "TEMPLATE_VOLTAGE": f"{row['Voltage [V]:']}V",
        "TEMPLATE_POWER": f"{float(row['Power [W]:'])*1000}mW",
        "TEMPLATE_TEMPCO": f"{row['TempCo [ppm]:']}ppm",
        "TEMPLATE_CURRENT": f"{row['Current [A]:']}A",
        "TEMPLATE_DESCRIPTION": description,
        "TEMPLATE_DATASHEET": row["Datasheet:"],
        "TEMPLATE_FOOTPRINT": row["Footprint:"],
        "TEMPLATE_TEMPLATE": template_name,
        "TEMPLATE_TYPE": row["Type:"],
    }
    sexpr = TEMPLATE
    for old, new in replacements.items():
        sexpr = sexpr.replace(old, new)

    new_symbol = kiutils.symbol.Symbol.from_sexpr(kiutils.utils.sexpr.parse_sexp(sexpr))
    logger.info(f"New symbol created. MPN: {row['MPN:']}")
    return new_symbol




TEMPLATE = """
(symbol "TEMPLATE_NAME"
        (extends "R")
        (property "Reference" "R"
                (at 0.762 0.508 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (justify left)
                )
        )
        (property "Value" "TEMPLATE_VALUE"
                (at 0.762 -1.016 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (justify left)
                )
        )
        (property "Footprint" "TEMPLATE_FOOTPRINT"
                (at 0 -15.24 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "Datasheet" "TEMPLATE_DATASHEET"
                (at 0 -20.32 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "Description" "TEMPLATE_DESCRIPTION"
                (at 0 -17.78 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "Tolerance" "TEMPLATE_TOLERANCE"
                (at 0 -25.4 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "TempCo" "TEMPLATE_TEMPCO"
            (at 0 -27.94 0)
            (effects
                    (font
                            (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "Type" "TEMPLATE_TYPE"
                (at 0 -10.16 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "Power" "TEMPLATE_POWER"
                (at 0 -33.02 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "Voltage" "TEMPLATE_VOLTAGE"
                (at 0 -38.1 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "Current" "TEMPLATE_CURRENT"
                (at 0 -35.56 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "MPN" "TEMPLATE_MPN"
                (at 0 -48.26 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "Mouser" "TEMPLATE_MOUSER"
            (at 0 -45.72 0)
            (effects
                    (font
                            (size 1.27 1.27)
                    )
                    (hide yes)
                )
        )
        (property "TME" "TEMPLATE_TME"
                (at 0 -43.18 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "LCSC" "TEMPLATE_LCSC"
                (at 0 -50.8 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "ki_keywords" "R resistor"
                (at 0 0 0)
                (effects
                        (font
                                (size 1.27 1.27)
                        )
                        (hide yes)
                )
        )
        (property "ki_fp_filters" "R_*"
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

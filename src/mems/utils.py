from dataclasses import dataclass
import os
import pathlib
import json
import re
import sys
import math
from typing import List
import xdg.BaseDirectory
from pathlib import Path

import termcolor
import requests
from bs4 import BeautifulSoup

LIBRARY_RESOURCE_NAME = "MEMS-scripts"


def get_main_sch():
    cwd = os.getcwd()
    path = pathlib.Path(cwd)
    sch = path / f"{path.stem}.kicad_sch"
    sch = sch.resolve()
    return str(sch)


def get_data_dir() -> Path:
    """Return directory where data is stored."""
    return Path(xdg.BaseDirectory.save_data_path(LIBRARY_RESOURCE_NAME))


def get_config():
    file_path = os.path.realpath(__file__)
    dir_path = pathlib.Path(file_path).parent
    config_path = dir_path.parent.parent / "config.json"
    if os.path.exists(config_path):
        with open(config_path) as fp:
            try:
                j = json.load(fp)
            except:
                sys.exit(termcolor.colored("Error: Couldn't parse config file", "red"))
    else:
        sys.exit(termcolor.colored("Error: Config file doesn't exist", "red"))

    return j


def search_mouser(val):
    api_key = get_api_key()
    data = json.dumps({"SearchByPartRequest": {"mouserPartNumber": val}})
    headers = {"Content-type": "application/json", "accept": "application/json"}
    r = requests.post(
        "https://api.mouser.com/api/v1/search/partnumber",
        params={"apiKey": api_key},
        data=data,
        headers=headers,
    )
    return r.json()


def get_api_key():
    if "MOUSER_API_KEY" in os.environ:
        return os.environ["MOUSER_API_KEY"]

    config = get_config()
    if "api_key" in config.keys():
        return config["api_key"]

    sys.exit(termcolor.colored('Error: No "api_key" found in config', "red"))


@dataclass
class PriceRow:
    moq: int
    unit_price: float


@dataclass
class LCSCItem:
    sku: str
    in_stock_qty: int
    prices: List[PriceRow]

    def get_price(self, qty):
        for row in self.prices:
            if row.moq <= qty:
                price = row.unit_price
        return price


def search_lcsc(sku):
    r = requests.get(
        "https://www.lcsc.com/search",
        params={"q": sku},
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
            "Accept": "text/html",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        },
    )
    soup = BeautifulSoup(r.content, "html.parser")

    if "Search by " in soup.title.string:
        return None

    qty_in_stock = int(soup.find("div", string=re.compile("In Stock:.*")).text.split(":")[1].strip())
    prices = list()
    price_table = soup.find(string=re.compile("Qty.*")).find_parent("table").tbody
    for row in price_table:
        tds = row.find_all("td")
        qty = int(re.findall("\d+", tds[0].string.strip())[0])
        unit_price = float(re.findall("\d+\.\d+", tds[1].span.string.strip())[0])
        prices.append(PriceRow(qty, unit_price))

    return LCSCItem(sku, qty_in_stock, prices)

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


def format_engineering(value: float, decimal_count: int = 2, as_separator: bool = False, unit: str | None = None) -> str:
    if value == 0:
        return "0" if unit is None else f"0{unit}"
    exponent = math.floor(math.log10(value))
    complete = math.floor(exponent // 3 * 3)
    remainder = exponent % 3
    if complete == 0:
        if unit is not None:
            prefix = unit
        else:
            prefix = ""
    else:
        prefix, _ = next(filter(lambda t: t[1] == complete, engineering_prefixes.items()))
    number = round(value * math.pow(10, remainder - exponent), decimal_count)
    if (number - math.floor(number)) > 1e-20:
        if as_separator:
            return f"{number}".replace(".", prefix).replace(",", prefix)  # Ugly solution
        return f"{number}{prefix}"
    return f"{int(number)}{prefix}"


if __name__ == "__main__":
    # search_lcsc("C5252902")
    search_lcsc("ala")

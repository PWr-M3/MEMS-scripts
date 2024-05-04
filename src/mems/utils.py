from dataclasses import dataclass
import os
import pathlib
import json
import re
import sys
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


if __name__ == "__main__":
    # search_lcsc("C5252902")
    search_lcsc("ala")

from dataclasses import dataclass
import os
import pathlib
import json
import re
import sys
import logging
import git
from typing import List
import xdg.BaseDirectory
from pathlib import Path
import termcolor
import requests
from bs4 import BeautifulSoup
from importlib import resources
import shutil

LIBRARY_RESOURCE_NAME = "MEMS-scripts"

logger = logging.getLogger(__name__)


def get_pro_filename() -> pathlib.Path | None:
    cwd = pathlib.Path(os.getcwd())
    pro_filename = next(cwd.rglob('*.kicad_pro'), None)
    if pro_filename is None:
        logger.error("Project file not found")
        return
    pro_filename = pro_filename.resolve()
    return pro_filename

def get_main_sch_filename():
    pro_filename = get_pro_filename()
    if pro_filename is None:
        return None
    sch_filename = pro_filename.with_suffix(".kicad_sch")
    if os.path.exists(sch_filename):
        return sch_filename
    else:
        logger.error("Main schematic file not found")
        return None

def get_main_pcb_filename():
    pro_filename = get_pro_filename()
    if pro_filename is None:
        return None
    pcb_filename = pro_filename.with_suffix(".kicad_pcb")
    if os.path.exists(pcb_filename):
        return pcb_filename
    else:
        logger.error("PCB file not found")
        return None


def get_data_dir() -> Path:
    """Return directory where data is stored."""
    return Path(xdg.BaseDirectory.save_data_path(LIBRARY_RESOURCE_NAME))


def get_config():
    config_path = get_data_dir() / "config.json"
    if not os.path.exists(config_path):
        traversable = resources.files("mems.data")
        with resources.as_file(traversable) as path:
            path = Path(path)
            shutil.copy(path / "config.json.template", config_path)

        logger.error(f"Error: Config file doesn't exist. Copying template to: {config_path}")
        sys.exit(1)

    with open(config_path) as config_file:
        try:
            config_json = json.load(config_file)
        except:
            logger.error(f"Couldn't parse config file: {config_path}. Fix the errors or delete the file to reinitialize")
            sys.exit(1)

    return config_json


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

def check_repo_clean(repo: git.Repo):
    """Stops program if repo is not clean."""
    if repo.is_dirty(untracked_files=True):
        logger.error("Repository is dirty. Aborting. Commit all changes before proceeding.")
        sys.exit(1)
    logger.debug("Repo is clean. Proceeding")

def set_text_variable(name: str, value: str):
    pro = get_pro_filename()
    if pro is None:
        sys.exit(1)
    with pro.open('r+') as pro_fp:

        j = json.load(pro_fp)
        variables = j.get("text_variables", None)
        if variables is None:
            j["text_variables"] = {}
            variables = j["text_variables"]
        variables[name] = value

        pro_fp.seek(0)
        json.dump(j, pro_fp, indent=2)
        pro_fp.truncate()



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
        qty = int(re.findall(r"\d+", tds[0].string.strip())[0])
        unit_price = float(re.findall(r"\d+\.\d+", tds[1].span.string.strip())[0])
        prices.append(PriceRow(qty, unit_price))

    return LCSCItem(sku, qty_in_stock, prices)

if __name__ == "__main__":
    # search_lcsc("C5252902")
    search_lcsc("ala")

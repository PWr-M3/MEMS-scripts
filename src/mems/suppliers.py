import logging
import json
import requests
import dataclasses
import re

from bs4 import BeautifulSoup, PageElement
from sane_logging import sys

logger = logging.getLogger(__name__)

# Rough currency estimates. Update if reeeaaallly out of date. Used only if no other option available:
CURRENCY_TO_PLN = {"PLN": 1.0, "USD": 4.0, "EUR": 4.3}


@dataclasses.dataclass
class PriceBreak:
    quantity: int
    price_pln: float


@dataclasses.dataclass
class Part:
    mpn: str
    sku: str
    description: str
    datasheet: str
    availability: int | None
    min_order_qty: int
    price_breaks: list[PriceBreak]

    def price_at_qty(self, quantity: int) -> float | None:
        price = next(filter(lambda x: x.quantity >= quantity, self.price_breaks), None)
        if price is None:
            return None
        return price.price_pln

    def cheapest_order(self, quantity: int) -> float | None:
        if quantity < self.min_order_qty:
            if not self.price_breaks:
                return None
            quantity = self.price_breaks[0].quantity
        price = self.price_at_qty(quantity)
        if price is None:
            return None

        return quantity * price


def price_break_from_mouser(data: dict) -> PriceBreak:
    quantity = int(data["Quantity"])
    price = float(data["Price"].split().replace(",", "."))
    price_pln = price * CURRENCY_TO_PLN[data["Currency"]]
    return PriceBreak(quantity=quantity, price_pln=price_pln)


def part_from_mouser(data: dict) -> Part:
    mpn = data["ManufacturerPartNumber"]
    sku = data["MouserPartNumber"]
    description = data["Description"]
    datasheet = data["DataSheetUrl"]
    availability = int(data["AvailabilityInStock"])
    min_order_qty = int(data["Min"])

    price_breaks = [price_break_from_mouser(price_break) for price_break in data["PriceBreaks"]]
    price_breaks = sorted(price_breaks, key=lambda x: x.quantity)

    return Part(mpn, sku, description, datasheet, availability, min_order_qty, price_breaks)


def search_mouser(query: str, api_key: str, exact: bool = False) -> list[Part]:
    data = json.dumps(
        {"SearchByPartRequest": {"mouserPartNumber": query, "partSearchOptions": "Exact" if exact else None}}
    )
    headers = {"Content-type": "application/json", "accept": "application/json"}
    r = requests.post(
        "https://api.mouser.com/api/v1/search/partnumber",
        params={"apiKey": api_key},
        data=data,
        headers=headers,
    )
    return [part_from_mouser(part) for part in r.json()["SearchResult"]["Parts"]]


def lcsc_get_field(soup: BeautifulSoup, query: str) -> PageElement | None:
    result = soup.find(string=re.compile(query))
    if result is not None and result.parent is not None and result.parent.parent is not None:
        tds = result.parent.parent.find_all("td")
        if len(tds) >= 2:
            return tds[1]
    return None


def search_lcsc(query: str) -> list[Part]:
    r = requests.get(
        "https://www.lcsc.com/search",
        params={"q": query},
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
            "Accept": "text/html",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        },
    )
    soup = BeautifulSoup(r.content, "html.parser")

    if soup.title is not None and soup.title.string is not None and "Search by " in soup.title.string:
        return []

    in_stock = soup.find("div", string=re.compile("In Stock:.*"))
    availability = None
    if in_stock is not None:
        availability = int(in_stock.text.split(":")[1].strip())
    prices = []
    qty_header = soup.find(string=re.compile("Qty.*"))
    if qty_header is not None:
        price_table = qty_header.find_parent("table")
        if price_table is not None and price_table.tbody is not None:
            for row in price_table.tbody.contents:
                tds = row.find_all("td")  # type: ignore
                qty = int(re.findall(r"\d+", tds[0].string.strip())[0])
                unit_price_usd = float(re.findall(r"\d+\.\d+", tds[1].span.string.strip())[0])
                prices.append(PriceBreak(qty, unit_price_usd * CURRENCY_TO_PLN["USD"]))

    mpn_q = lcsc_get_field(soup, r"Mfr. Part *")
    if mpn_q is None:
        sys.exit("MPN not found on LCSC site")
    mpn = mpn_q.text.strip()

    sku_q = lcsc_get_field(soup, "LCSC Part #")
    if sku_q is None:
        sys.exit("SKU not found on LCSC site")
    sku = sku_q.text.strip()

    desc_q = lcsc_get_field(soup, "Description")
    if desc_q is None:
        sys.exit("Description not found on LCSC site")
    desc = desc_q.text.strip()

    data_q = lcsc_get_field(soup, "Datasheet")
    if data_q is None or data_q.a is None:  # type: ignore
        sys.exit("Datasheet not found on LCSC site")
    data = data_q.a.attrs["href"]  # type: ignore

    min_q = soup.find(string=re.compile("Minimum : *"))
    if min_q is None:
        sys.exit("Minimum order quantity not found on LCSC site")
    minimum = int(min_q.split()[-1])  # type: ignore

    return [Part(mpn, sku, desc, data, availability, minimum, prices)]

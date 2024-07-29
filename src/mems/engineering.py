import math
import unittest

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
            if parsed[-1] == prefix:
                parsed = parsed[:-1]
            else:
                parsed = parsed.replace(prefix, ".")
    value = float(parsed)
    return value * multiplier


def parse_engineering_with_unit(parsed: str) -> tuple[float, str]:
    for prefix in engineering_prefixes.keys():
        if prefix in parsed:
            index = parsed.find(prefix)
            number = parsed[: index + 1]
            unit = parsed[index + 1 :]
            return (parse_engineering(number), unit)

    return (
        parse_engineering("".join(ch for ch in parsed if ch.isdigit() or ch in ".,")),
        "".join(ch for ch in parsed if not ch.isdigit() and ch not in ".,"),
    )


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


class TestParsing(unittest.TestCase):
    def test_parsing(self):
        equals = {
            "1T23": 1.23e12,
            "123G": 123e9,
            "123M2": 123.2e6,
            "0k1": 0.1e3,
            "0.1": 0.1,
            "0m23": 0.23e-3,
            "1u": 1e-6,
            "1.1n": 1.1e-9,
            "0.99p": 0.99e-12,
            ".1f": 0.1e-15,
        }
        for key, value in equals.items():
            self.assertAlmostEqual(parse_engineering(key), value)

    def test_parsing_with_units(self):
        equals = {
            "123kg": (123e3, "g"),
            ".1N": (0.1, "N"),
            "2mm": (2e-3, "m"),
        }
        for key, value in equals.items():
            number, unit = parse_engineering_with_unit(key)
            self.assertEqual(unit, value[1])
            self.assertAlmostEqual(number, value[0])

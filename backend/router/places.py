"""Cities the router can recognise in a question, with Urdu names and spelling variants.

Same eight cities as the website's map (frontend/lib/cities.ts); five of them (Karachi, Lahore, Multan, Peshawar,
Quetta) are also the markets in the price data.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    id: str
    name: str
    urdu: str
    lat: float
    lon: float
    aliases: tuple[str, ...]


CITIES: list[City] = [
    City("peshawar", "Peshawar", "پشاور", 34.01, 71.52, ("peshawar", "pashawar", "پشاور")),
    City("islamabad", "Islamabad", "اسلام آباد", 33.68, 73.05, ("islamabad", "اسلام آباد", "اسلام‌آباد")),
    City("lahore", "Lahore", "لاہور", 31.52, 74.36, ("lahore", "لاہور")),
    City("faisalabad", "Faisalabad", "فیصل آباد", 31.42, 73.08, ("faisalabad", "فیصل آباد", "فیصل‌آباد")),
    City("multan", "Multan", "ملتان", 30.2, 71.47, ("multan", "ملتان")),
    City("quetta", "Quetta", "کوئٹہ", 30.18, 66.99, ("quetta", "koita", "کوئٹہ", "کوئٹا")),
    City("hyderabad", "Hyderabad", "حیدرآباد", 25.39, 68.37, ("hyderabad", "حیدرآباد", "حیدر آباد")),
    City("karachi", "Karachi", "کراچی", 24.86, 67.0, ("karachi", "کراچی")),
]
BY_NAME = {c.name: c for c in CITIES}


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def nearest(lat: float, lon: float, names: list[str]) -> City:
    """The city (among `names`) closest to a point."""
    return min((BY_NAME[n] for n in names), key=lambda c: km_between(lat, lon, c.lat, c.lon))

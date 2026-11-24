import re
from decimal import Decimal

from app.config import WAVELENGTH_MAX_NM, WAVELENGTH_MIN_NM

NUMBER = re.compile(r'[+-]?\d+(?:\.\d{1,6})?', re.ASCII)
DISTANCE = {'m': 1000, 'km': 1_000_000, 'mm': 1}


def scaled(text, factor, minimum, maximum):
    if len(text) > 24 or not NUMBER.fullmatch(text):
        raise ValueError('BAD_NUMERIC')
    value = Decimal(text) * factor
    if value != value.to_integral_value() or not minimum <= value <= maximum:
        raise ValueError('OUT_OF_SCALE')
    return int(value)


def distance(value, unit):
    if unit not in DISTANCE:
        raise ValueError('DISTANCE_UNIT')
    return scaled(value, DISTANCE[unit], 0, 500_000_000)


def wavelength(text):
    if len(text) not in (3, 4) or not text.isascii() or not text.isdigit():
        raise ValueError('BAD_WAVELENGTH')
    value = int(text)
    if not WAVELENGTH_MIN_NM <= value <= WAVELENGTH_MAX_NM:
        raise ValueError('BAD_WAVELENGTH')
    return value

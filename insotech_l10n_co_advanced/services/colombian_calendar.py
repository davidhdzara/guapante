# -*- coding: utf-8 -*-
"""Colombian Business Days Calculator.

Pure Python implementation of the Colombian holiday calendar.
Supports all 18 official holidays including:
- Fixed-date holidays
- Ley Emiliani holidays (moved to Monday)
- Easter-dependent holidays (Gauss algorithm)

Manual holiday override via set union (duplicates are ignored).

Legal basis:
- Ley 51 de 1983 (Colombian holidays)
- Art. 62, Ley 4 de 1913 (business days definition)
- Resolución 000165 de 2023, art. 25 (RADIAN tacit acceptance)
"""

from datetime import date, timedelta


def _easter(year):
    """Compute Easter Sunday date using the Anonymous Gregorian algorithm.

    This is the standard algorithm used by most calendar libraries.

    :param year: The year to compute Easter for
    :returns: date object for Easter Sunday
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l_val = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_val) // 451
    month = (h + l_val - 7 * m + 114) // 31
    day = ((h + l_val - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _next_monday(dt):
    """Move a date to the next Monday (Ley Emiliani).

    If the date is already a Monday, return it unchanged.
    Otherwise, move to the following Monday.

    :param dt: date object
    :returns: date object (Monday)
    """
    weekday = dt.weekday()  # 0=Monday
    if weekday == 0:
        return dt
    return dt + timedelta(days=(7 - weekday))


def get_colombian_holidays(year):
    """Compute all 18 official Colombian holidays for the given year.

    Returns a set of date objects. Holidays are categorized as:

    **Fixed-date holidays (not moved):**
    - Jan 1: Año Nuevo
    - May 1: Día del Trabajo
    - Jul 20: Grito de Independencia
    - Aug 7: Batalla de Boyacá
    - Dec 8: Inmaculada Concepción
    - Dec 25: Navidad

    **Ley Emiliani holidays (moved to next Monday):**
    - Jan 6: Reyes Magos
    - Mar 19: San José
    - Jun 29: San Pedro y San Pablo
    - Aug 15: Asunción de la Virgen
    - Oct 12: Día de la Raza
    - Nov 1: Todos los Santos
    - Nov 11: Independencia de Cartagena

    **Easter-dependent holidays:**
    - Jueves Santo (Easter - 3)
    - Viernes Santo (Easter - 2)
    - Ascensión del Señor (Easter + 43, moved to Monday)
    - Corpus Christi (Easter + 64, moved to Monday)
    - Sagrado Corazón (Easter + 71, moved to Monday)

    :param year: Year to compute holidays for
    :returns: set of date objects
    """
    easter = _easter(year)

    holidays = {
        # --- Fixed-date holidays ---
        date(year, 1, 1),    # Año Nuevo
        date(year, 5, 1),    # Día del Trabajo
        date(year, 7, 20),   # Grito de Independencia
        date(year, 8, 7),    # Batalla de Boyacá
        date(year, 12, 8),   # Inmaculada Concepción
        date(year, 12, 25),  # Navidad

        # --- Ley Emiliani holidays (move to Monday) ---
        _next_monday(date(year, 1, 6)),    # Reyes Magos
        _next_monday(date(year, 3, 19)),   # San José
        _next_monday(date(year, 6, 29)),   # San Pedro y San Pablo
        _next_monday(date(year, 8, 15)),   # Asunción de la Virgen
        _next_monday(date(year, 10, 12)),  # Día de la Raza
        _next_monday(date(year, 11, 1)),   # Todos los Santos
        _next_monday(date(year, 11, 11)),  # Independencia de Cartagena

        # --- Easter-dependent holidays ---
        easter - timedelta(days=3),         # Jueves Santo
        easter - timedelta(days=2),         # Viernes Santo
        _next_monday(                       # Ascensión del Señor
            easter + timedelta(days=43)
        ),
        _next_monday(                       # Corpus Christi
            easter + timedelta(days=64)
        ),
        _next_monday(                       # Sagrado Corazón
            easter + timedelta(days=71)
        ),
    }

    return holidays


def is_business_day(dt, extra_holidays=None):
    """Check if a date is a Colombian business day.

    A business day is any day that is NOT:
    - Saturday
    - Sunday
    - An official Colombian holiday
    - A manually-added custom holiday

    :param dt: date object to check
    :param extra_holidays: optional set of additional date objects
    :returns: True if the date is a business day
    """
    # Weekends
    if dt.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return False

    # Official holidays
    holidays = get_colombian_holidays(dt.year)

    # Merge manual holidays (set union = auto-dedup)
    if extra_holidays:
        holidays = holidays | extra_holidays

    return dt not in holidays


def add_business_days(start, n, extra_holidays=None):
    """Add N business days to a start date.

    Skips weekends, official Colombian holidays, and any
    manually-added custom holidays.

    :param start: date object (starting date, not counted)
    :param n: number of business days to add (must be >= 0)
    :param extra_holidays: optional set of additional date objects
    :returns: date object N business days after start
    """
    if n < 0:
        raise ValueError("n must be >= 0")
    if n == 0:
        return start

    current = start
    counted = 0

    while counted < n:
        current += timedelta(days=1)
        if is_business_day(current, extra_holidays):
            counted += 1

    return current

import re


def safe_text(content):
    """Extract plain text from an AIMessage content that may be str or list[dict]."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


_INDIAN_NUMBER_RE = re.compile(
    r"^(?P<value>[\d.]+)\s*(?P<unit>lakh|L|crore|Cr|cr|k|K)?$"
)

_CRORE = 10_000_000
_LAKH = 100_000
_THOUSAND = 1_000


def parse_budget(raw: object) -> float | None:
    """Convert a budget value that may contain Indian currency shorthand to
    a plain float in rupees.

    Handles ``"80 lakh"``, ``"80L"``, ``"1.2 crore"``, ``"1.2 Cr"``,
    ``"1.2cr"``, ``"50k"``, and plain numbers.  Strips ``₹``, commas,
    and whitespace first.  Returns *None* for unparseable input.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)

    cleaned = str(raw).replace("₹", "").replace(",", "").strip()
    if not cleaned:
        return None

    m = _INDIAN_NUMBER_RE.match(cleaned)
    if not m:
        return None

    try:
        value = float(m.group("value"))
    except ValueError:
        return None

    unit = (m.group("unit") or "").lower()
    if unit == "cr" or unit == "crore":
        return value * _CRORE
    if unit == "l":
        return value * _LAKH
    if unit == "lakh":
        return value * _LAKH
    if unit == "k":
        return value * _THOUSAND

    return value

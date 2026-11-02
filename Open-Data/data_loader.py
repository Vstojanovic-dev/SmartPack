"""Prenos in osnovno branje tabele SURS 2164466S v formatu PC-Axis (.px).

Zaradi velikosti izvirne tabele (približno 2 milijona celic) beremo le
meritev 'Prihodi turistov' za skupno državo izvora. Ne seštevamo vmesnih
seštevkov ('domači', 'tuji') z njihovimi podskupinami.
"""

from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
import requests

SOURCE_PAGE = "https://podatki.gov.si/dataset/surs2164466s"
PX_URL = "https://pxweb.stat.si/SiStatData/Resources/PX/Databases/Data/2164466S.PX"

# Izrazi so omejeni na ključne elemente PC-Axis, ki jih uporablja tabela SURS.
_DATA_START = re.compile(r"(?im)^\s*DATA\s*=")
_METADATA_STATEMENT = re.compile(
    r'(?ims)^\s*(STUB|HEADING|VALUES)\s*(?:\(\s*("[^"]+")\s*\))?\s*='
    r'\s*((?:"(?:[^"]|"")*"|[^";])*)\s*;'
)
_QUOTED = re.compile(r'"((?:[^"]|"")*)"')
_DATA_TOKEN = re.compile(r'"[^"]*"|[^\s,;]+')
_PERIOD = re.compile(r"^(20\d{2})M(0[1-9]|1[0-2])$")


class PXFormatError(ValueError):
    """Datoteka ni veljavna/ustrezna tabela PC-Axis za aplikacijo."""


def decode_px(raw: bytes) -> str:
    """Prepozna UTF-8 in pogosto srednjeevropsko ANSI kodiranje SURS."""
    if not raw:
        raise PXFormatError("Datoteka PX je prazna.")
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise PXFormatError("Kodiranja datoteke PX ni mogoče prebrati.")


def parse_px(raw: bytes) -> pd.DataFrame:
    """Vrne le stolpce 'godina', 'mesec', 'obcina', 'prihodi' iz izvirnega PX.

    Vrsti red celic izračuna iz STUB in HEADING (ne predpostavlja vrstnega
    reda v datoteki). Manjkajočih celic ne pretvarja v ničle.
    """
    content = decode_px(raw)
    match = _DATA_START.search(content)
    if not match:
        raise PXFormatError("Manjka del DATA v datoteki PC-Axis.")
    metadata = content[: match.start()]
    if re.search(r"(?im)^\s*KEYS(?:\s*\(|\s*=)", metadata):
        raise PXFormatError("Datoteka PX s ključem KEYS ni podprta.")
    tail = content[match.end():].strip()
    if not tail.endswith(";"):
        raise PXFormatError("Del DATA nima zaključnega podpičja.")
    # DATA je zadnje polje PC-Axis; ločila in prazne vrstice so dovoljena.
    data_section = tail[:-1]

    axes: list[str] = []
    values: dict[str, list[str]] = {}
    for statement in _METADATA_STATEMENT.finditer(metadata):
        key, argument, body = statement.groups()
        strings = [s.replace('""', '"') for s in _QUOTED.findall(body)]
        if key.upper() in ("STUB", "HEADING"):
            axes.extend(strings)
        elif argument:
            name = argument.strip('"')
            values[name] = strings

    needed = {"MESEC", "OBČINE", "DRŽAVA", "MERITVE"}
    if set(axes) != needed or len(axes) != 4:
        raise PXFormatError(f"Nepričakovane dimenzije PC-Axis: {axes!r}.")
    if any(not values.get(axis) for axis in axes):
        raise PXFormatError("Manjkajo vrednosti ene ali več dimenzij.")

    country_options = values["DRŽAVA"]
    measure_options = values["MERITVE"]
    country_index = next(
        (i for i, label in enumerate(country_options)
         if label.strip().casefold().startswith("0 država") and "skupaj" in label.casefold()),
        None,
    )
    # Rezultati prikazujejo skupno število prihodov (ne števila nočitev).
    measure_index = next(
        (i for i, label in enumerate(measure_options)
         if label.strip().casefold() == "prihodi turistov"),
        None,
    )
    if country_index is None or measure_index is None:
        raise PXFormatError("Ni skupne države izvora ali meritve 'Prihodi turistov'.")

    lengths = {axis: len(values[axis]) for axis in axes}
    strides: dict[str, int] = {}
    product = 1
    for axis in reversed(axes):
        strides[axis] = product
        product *= lengths[axis]

    # Iz vseh celic (vključno z državami izvora in nočitvami) izberemo samo
    # indekse želene meritve. Tako ne gradimo ogromnega DataFrame-a.
    selected: dict[int, tuple[int, int, str]] = {}
    for month_idx, period in enumerate(values["MESEC"]):
        parsed_period = _PERIOD.fullmatch(period.strip())
        if not parsed_period:
            continue
        year, month = map(int, parsed_period.groups())
        for muni_idx, municipality in enumerate(values["OBČINE"]):
            if municipality.strip().upper() == "SLOVENIJA":
                continue  # Državni seštevek ni občina.
            position = (
                month_idx * strides["MESEC"]
                + muni_idx * strides["OBČINE"]
                + country_index * strides["DRŽAVA"]
                + measure_index * strides["MERITVE"]
            )
            selected[position] = (year, month, municipality.strip())

    rows: list[tuple[int, int, str, int]] = []
    cell_count = 0
    for cell_count, token_match in enumerate(_DATA_TOKEN.finditer(data_section), start=1):
        info = selected.get(cell_count - 1)
        if info is None:
            continue
        value = token_match.group().strip('"')
        # PX vrednosti '.', '..', '...' ali '-' označujejo manjkajoče podatke.
        if value in {".", "..", "...", "....", ".....", "......", "-", ":"}:
            continue
        if not re.fullmatch(r"\d+", value):
            raise PXFormatError(f"Nepričakovana vrednost za prihode turistov: {value!r}.")
        rows.append((*info, int(value)))

    if cell_count != product:
        raise PXFormatError(
            f"Neujemanje števila celic: pričakovano {product}, prebrano {cell_count}."
        )
    if not rows:
        raise PXFormatError("Tabela PX ne vsebuje uporabnih podatkov o prihodih turistov.")
    return pd.DataFrame(rows, columns=["godina", "mesec", "obcina", "prihodi"])


def download_data(timeout: int = 60) -> pd.DataFrame:
    """Ob vsakem klicu prenese pravo datoteko .PX in jo pretvori v tabelo."""
    try:
        response = requests.get(
            PX_URL,
            timeout=timeout,
            headers={"User-Agent": "SmartPack-TIDS-StudentProject/1.0 (educational use)",
                     "Accept": "application/octet-stream, text/plain, */*"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Prenos podatkov SURS ni uspel: {exc}") from exc
    return parse_px(response.content)


def available_years(df: pd.DataFrame, current_year: int | None = None) -> list[int]:
    """Tekoče leto in največ šest predhodnih (kolikor so na voljo)."""
    year = current_year if current_year is not None else datetime.now().year
    return sorted(
        (int(y) for y in df["godina"].unique() if year - 6 <= int(y) <= year),
        reverse=True,
    )


def available_months(df: pd.DataFrame, year: int) -> list[int]:
    return sorted(int(m) for m in df.loc[df["godina"] == year, "mesec"].unique())


def top_ten(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Razvrsti občine glede na skupno število prihodov za izbrani mesec."""
    chosen = df.loc[(df["godina"] == year) & (df["mesec"] == month)]
    result = (chosen.groupby("obcina", as_index=False)["prihodi"]
              .sum().sort_values(["prihodi", "obcina"], ascending=[False, True]))
    return result.head(10).reset_index(drop=True)


def monthly_trend(df: pd.DataFrame, municipality: str, year: int) -> pd.DataFrame:
    """12 mesecev: še neobjavljeni meseci ostanejo NaN, ne nič."""
    chosen = df.loc[(df["godina"] == year) & (df["obcina"] == municipality)]
    result = chosen.groupby("mesec")["prihodi"].sum().reindex(range(1, 13))
    return pd.DataFrame({"mesec": list(range(1, 13)), "prihodi": result.to_numpy()})


def comparison_trend(
    df: pd.DataFrame, first_municipality: str, second_municipality: str, year: int
) -> pd.DataFrame:
    """Združi mesečna prihoda dveh občin na isto časovno os (1–12)."""
    if first_municipality == second_municipality:
        raise ValueError("Za primerjavo izberite dve različni občini.")
    first = monthly_trend(df, first_municipality, year).rename(
        columns={"prihodi": first_municipality}
    )
    second = monthly_trend(df, second_municipality, year).rename(
        columns={"prihodi": second_municipality}
    )
    return first.merge(second, on="mesec", validate="one_to_one")

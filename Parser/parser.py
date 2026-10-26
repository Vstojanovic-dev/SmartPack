"""SmartPack: extract packing items from the public Wikivoyage HTML article."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser

import requests
from bs4 import BeautifulSoup


SOURCE_URL = "https://en.wikivoyage.org/wiki/Packing_list"
ROBOTS_URL = "https://en.wikivoyage.org/robots.txt"
OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "packing_data.json"
TIMEOUT = (5, 15)  # Connection timeout, read timeout (seconds).

# Only article headings supply category names; no packing items are hardcoded.
EXCLUDED_SECTIONS = {"see also", "references", "external links", "notes"}
UNRELATED_ELEMENTS = (
    "nav, aside, footer, script, style, .toc, #toc, .mw-editsection, "
    ".reference, .reflist, .navbox, .infobox, .metadata, .thumb, "
    ".hatnote, .noprint, .printfooter, .catlinks"
)


class ParserError(Exception):
    """Readable error for an unavailable or unexpectedly structured page."""


def normalize(text):
    """Remove extra whitespace while preserving the source language."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def make_user_agent():
    """Identify this script and provide a real operator contact as Wikimedia asks."""
    contact = os.environ.get("SMARTPACK_CONTACT", "").strip()
    if not contact:
        try:
            contact = input(
                "Kontakt za Wikimedia User-Agent (e-pošta ali URL vašega repozitorija): "
            ).strip()
        except EOFError as exc:
            raise ParserError(
                "Nastavite SMARTPACK_CONTACT na svoj e-poštni naslov ali URL repozitorija."
            ) from exc

    if not contact or " " in contact or not (
        "@" in contact or contact.startswith("https://")
    ):
        raise ParserError(
            "Neveljaven kontakt. Vnesite e-poštni naslov ali URL, ki se začne s https://."
        )
    return f"SmartPackParser/1.0 ({contact}; educational TIDS HTML parser) python-requests"


def download_html(user_agent):
    """Check robots.txt first, then make one request for the article (no API)."""
    headers = {"User-Agent": user_agent, "Accept": "text/html"}
    try:
        with requests.Session() as session:
            session.headers.update(headers)
            robots_response = session.get(ROBOTS_URL, timeout=TIMEOUT)
            robots_response.raise_for_status()

            robots = robotparser.RobotFileParser()
            robots.parse(robots_response.text.splitlines())
            if not robots.can_fetch(user_agent, SOURCE_URL):
                raise ParserError("Datoteka robots.txt ne dovoljuje dostopa do izbrane strani.")

            response = session.get(SOURCE_URL, timeout=TIMEOUT)
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                raise ParserError("Strežnik ni vrnil HTML dokumenta.")
            return response.content
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        raise ParserError(
            f"Napaka HTTP {status}. Dostopa ne poskušamo zaobiti; poskusite kasneje."
        ) from exc
    except requests.RequestException as exc:
        raise ParserError(f"Napaka pri prenosu strani ali robots.txt: {exc}") from exc


def extract_item(li):
    """Get the item's label from a real list bullet, without losing long labels."""
    # Nested bullets are handled separately; explanations after a dash/semicolon
    # are not part of the name of the item.
    copy = BeautifulSoup(str(li), "html.parser").find("li")
    for nested in copy.find_all(["ul", "ol", "sup"]):
        nested.decompose()
    text = normalize(copy.get_text(" ", strip=True))
    if not text:
        return ""

    title = re.split(r"\s+[\u2013\u2014-]\s+", text, maxsplit=1)[0]
    title = title.split(";", 1)[0]

    # Some Wikivoyage bullets begin with a clear subject and then explain it:
    # "Ear plugs are useful ..." -> "Ear plugs". No arbitrary length limit.
    subject = re.match(
        r"^(.+?)\s+(?:is|are)\s+(?:useful|good|handy|perhaps|recommended|necessary)\b",
        title,
        flags=re.IGNORECASE,
    )
    if subject:
        title = subject.group(1)
    return normalize(title).strip(" :;.,")


# Paragraphs are free-form prose, so only explicit, sentence-initial advice is
# accepted. This is a grammar pattern, not a prewritten list of packing items.
PACKING_ADVICE_PREFIX = (
    r"(?:bring(?: along)?|pack|carry|take along|"
    r"consider (?:bringing|packing|taking)|"
    r"(?:don't|do not) forget to (?:bring|pack)|"
    r"remember to (?:bring|pack|carry)|"
    r"you (?:may|might) (?:want|prefer) to (?:bring|pack)|"
    r"you(?:'ll| will) probably want to bring)\s+"
)
PACKING_ADVICE = re.compile(
    r"^" + PACKING_ADVICE_PREFIX + r"(.+)$",
    flags=re.IGNORECASE,
)


def extract_paragraph_items(paragraph):
    """Return only clearly worded packing recommendations, not general prose."""
    text = normalize(paragraph.get_text(" ", strip=True))
    items = []
    # A paragraph can contain several independently worded recommendations.
    # Also accept lowercase advice after a sentence boundary. An initial such
    # as the final S. in U.S. must not split an item's name.
    boundary = (
        r"(?<!\b[A-Z]\.)(?<=[.!?])\s+"
        r"(?=[A-Z]|(?i:" + PACKING_ADVICE_PREFIX + r"))"
    )
    for sentence in re.split(boundary, text):
        match = PACKING_ADVICE.match(sentence)
        if not match:
            continue
        item = match.group(1).strip(" :;.,!?")
        # Remove trailing explanatory clauses only when they are clearly separate.
        item = re.split(
            r",?\s+(?:because|unless|in case|so that)\b",
            item, maxsplit=1, flags=re.IGNORECASE,
        )[0].strip(" :;.,!?")
        # Do not turn generic instructions ("bring stuff", "take half ...")
        # into alleged names of objects.
        if not item or re.match(
            r"^(?:stuff|things|anything|everything|what|only|half|all|yourself)\b",
            item,
            flags=re.IGNORECASE,
        ):
            continue
        items.append(item)
    return items


def parse_packing_html(html):
    """Walk real article headings, HTML lists and explicit paragraph advice."""
    soup = BeautifulSoup(html, "html.parser")
    article = (
        soup.select_one("#mw-content-text .mw-parser-output")
        or soup.select_one("main .mw-parser-output")
        or soup.select_one("#mw-content-text")
    )
    if article is None:
        raise ParserError("Glavne vsebine članka (#mw-content-text) ni bilo mogoče najti.")

    for irrelevant in article.select(UNRELATED_ELEMENTS):
        irrelevant.decompose()

    headings = {}
    categories = {}
    globally_seen = set()

    # Modern MediaWiki may wrap headings in .mw-heading; h2/h3/h4 still carry
    # their text. Read only the article, never the page-wide menus or sidebar.
    for element in article.find_all(["h2", "h3", "h4", "ul", "ol", "p"]):
        if element.name in {"h2", "h3", "h4"}:
            level = int(element.name[1])
            headline = element.select_one(".mw-headline") or element
            title = normalize(headline.get_text(" ", strip=True))
            for previous_level in list(headings):
                if previous_level >= level:
                    del headings[previous_level]
            if title:
                headings[level] = title
            continue

        if not headings or any(
            title.casefold() in EXCLUDED_SECTIONS for title in headings.values()
        ):
            continue
        category_name = " / ".join(headings[level] for level in sorted(headings))

        if element.name in {"ul", "ol"}:
            candidates = [extract_item(li) for li in element.find_all("li", recursive=False)]
        elif element.find_parent("li") is None:
            candidates = extract_paragraph_items(element)
        else:
            continue  # Do not parse prose inside a bullet a second time.

        for item in candidates:
            key = normalize(item).casefold()
            if item and key not in globally_seen:
                categories.setdefault(category_name, []).append(item)
                globally_seen.add(key)

    result = [{"name": name, "items": items} for name, items in categories.items() if items]
    if not result:
        raise ParserError(
            "V članku ni bilo najdenih ustreznih predmetov za pakiranje. "
            "Preverite, ali se je HTML struktura Wikivoyage spremenila."
        )
    return result


def save_json(categories):
    """Write a validated temporary file and replace old JSON only on success."""
    data = {
        "source": "Wikivoyage",
        "attribution": "Wikivoyage contributors (see the article and its history)",
        "source_url": SOURCE_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "type": "general_packing",
        "license": "CC BY-SA 4.0",
        "categories": categories,
    }
    if not isinstance(categories, list) or not categories or any(
        not isinstance(category, dict)
        or not isinstance(category.get("name"), str)
        or not category["name"].strip()
        or not isinstance(category.get("items"), list)
        or not category["items"]
        or any(not isinstance(item, str) or not item.strip() for item in category["items"])
        for category in categories
    ):
        raise ParserError("Ni veljavnih kategorij in predmetov; stari JSON ostane nespremenjen.")
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    json.loads(serialized)  # Check that the serialization is valid before touching old data.

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = OUTPUT_FILE.with_name(OUTPUT_FILE.name + ".tmp")
    try:
        temporary_file.write_text(serialized, encoding="utf-8")
        json.loads(temporary_file.read_text(encoding="utf-8"))
        temporary_file.replace(OUTPUT_FILE)  # Atomic when the files share a filesystem.
    finally:
        temporary_file.unlink(missing_ok=True)
    return OUTPUT_FILE


def main():
    try:
        user_agent = make_user_agent()
        html = download_html(user_agent)
        categories = parse_packing_html(html)
        output = save_json(categories)
    except (ParserError, OSError, ValueError) as exc:
        print(f"Napaka: {exc}")
        return 1

    total_items = sum(len(category["items"]) for category in categories)
    print("Wikivoyage HTML je bil uspešno razčlenjen.")
    print(f"Kategorije: {len(categories)} | Predmeti: {total_items}")
    print(f"Datoteka: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

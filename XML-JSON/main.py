"""SmartPack: povezovanje lokalnih podatkov XML ter izvoz v JSON in XML."""

import argparse
from datetime import date
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


MAPA_PROJEKTA = Path(__file__).resolve().parent
MAPA_PODATKOV = MAPA_PROJEKTA / "data"
DOVOLJENA_PRTLJAGA = {"rocna", "oddana", "nahrbtnik"}


class NapakaPodatkov(Exception):
    """Razumljivo sporočilo o nepravilnih vhodnih podatkih."""


class SlovenskiParser(argparse.ArgumentParser):
    """Slovenska pomoč in sporočila ob napačnih argumentih."""

    def format_usage(self):
        return super().format_usage().replace("usage:", "Uporaba:")

    def format_help(self):
        return (super().format_help()
                .replace("usage:", "Uporaba:")
                .replace("options:", "Možnosti:"))

    def error(self, message):
        message = (message.replace("unrecognized arguments:", "Neprepoznani argumenti:")
                   .replace("expected one argument", "manjka vrednost argumenta"))
        self.print_usage(sys.stderr)
        self.exit(2, f"Napaka pri argumentih: {message}\n")


def preveri_datum(vrednost):
    """Preveri datum in vrne objekt date; dovoljena je samo oblika LLLL-MM-DD."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", vrednost or ""):
        raise ValueError("Datum mora biti v obliki YYYY-MM-DD.")
    try:
        return date.fromisoformat(vrednost)
    except ValueError as napaka:
        raise ValueError(f"Datum '{vrednost}' ne obstaja.") from napaka


def datum_argument(vrednost):
    try:
        return preveri_datum(vrednost)
    except ValueError as napaka:
        raise argparse.ArgumentTypeError(str(napaka)) from napaka


def obvezen_atribut(element, ime):
    vrednost = element.get(ime)
    if not vrednost or not vrednost.strip():
        raise NapakaPodatkov(f"Element <{element.tag}> nima obveznega atributa '{ime}'.")
    return vrednost.strip()


def besedilo(element, ime, obvezno=True):
    polje = element.find(ime)
    vrednost = polje.text.strip() if polje is not None and polje.text else ""
    if obvezno and not vrednost:
        ident = element.get("id", "brez ID")
        raise NapakaPodatkov(f"Zapis {ident}: manjka obvezno polje <{ime}>.")
    return vrednost or None


def stevilo(element, ime, celo=False, pozitivno=False):
    vrednost = besedilo(element, ime)
    try:
        rezultat = int(vrednost) if celo else float(vrednost)
    except (TypeError, ValueError) as napaka:
        raise NapakaPodatkov(f"Zapis {element.get('id')}: polje <{ime}> ni veljavno število.") from napaka
    if not math.isfinite(rezultat) or (pozitivno and rezultat <= 0):
        raise NapakaPodatkov(f"Zapis {element.get('id')}: polje <{ime}> mora biti končno pozitivno število.")
    return rezultat


def datum_polja(element, ime, obvezno=True):
    vrednost = besedilo(element, ime, obvezno=obvezno)
    if vrednost is None:
        return None
    try:
        preveri_datum(vrednost)
    except ValueError as napaka:
        raise NapakaPodatkov(f"Zapis {element.get('id')}, polje <{ime}>: {napaka}") from napaka
    return vrednost


def odpri_xml(pot, koren):
    try:
        drevo = ET.parse(pot)
    except FileNotFoundError as napaka:
        raise NapakaPodatkov(f"Vhodna datoteka ne obstaja: {pot.name}.") from napaka
    except (ET.ParseError, UnicodeError) as napaka:
        raise NapakaPodatkov(f"Datoteka {pot.name} ni veljaven XML: {napaka}") from napaka
    except OSError as napaka:
        raise NapakaPodatkov(f"Datoteke {pot.name} ni mogoče prebrati: {napaka}") from napaka
    if drevo.getroot().tag != koren:
        raise NapakaPodatkov(f"Datoteka {pot.name} mora imeti korenski element <{koren}>.")
    return drevo.getroot()


def dodaj_unikaten(zbirka, zapis, vrsta):
    ident = zapis["id"]
    if ident in zbirka:
        raise NapakaPodatkov(f"Podvojen ID '{ident}' v datoteki {vrsta}.")
    zbirka[ident] = zapis


def nalozi_podatke(mapa_podatkov=MAPA_PODATKOV):
    """Razčleni tri datoteke, preveri ID-je in vrne povezane podatke."""
    mapa_podatkov = Path(mapa_podatkov)
    destinacije = {}
    koren = odpri_xml(mapa_podatkov / "destinacije.xml", "destinacije")
    for element in koren.findall("destinacija"):
        zapis = {
            "id": obvezen_atribut(element, "id"),
            "naziv": besedilo(element, "naziv"),
            "drzava": besedilo(element, "drzava"),
            "povprecna_temperatura": stevilo(element, "povprecnaTemperatura", celo=True),
            "opis": besedilo(element, "opis", obvezno=False),
            "datum_zadnjega_obiska": datum_polja(element, "datumZadnjegaObiska", obvezno=False),
        }
        dodaj_unikaten(destinacije, zapis, "destinacije.xml")

    aktivnosti = {}
    koren = odpri_xml(mapa_podatkov / "aktivnosti.xml", "aktivnosti")
    for element in koren.findall("aktivnost"):
        zapis = {
            "id": obvezen_atribut(element, "id"),
            "destinacija_id": obvezen_atribut(element, "destinacijaId"),
            "naziv": besedilo(element, "naziv"),
            "kategorija": besedilo(element, "kategorija"),
            "trajanje_ur": stevilo(element, "trajanjeUr", celo=True, pozitivno=True),
            "opis": besedilo(element, "opis", obvezno=False),
        }
        dodaj_unikaten(aktivnosti, zapis, "aktivnosti.xml")
        if zapis["destinacija_id"] not in destinacije:
            raise NapakaPodatkov(
                f"Aktivnost {zapis['id']} se sklicuje na neobstoječo destinacijo {zapis['destinacija_id']}."
            )

    potovanja = {}
    koren = odpri_xml(mapa_podatkov / "potovanja.xml", "potovanja")
    for element in koren.findall("potovanje"):
        ident = obvezen_atribut(element, "id")
        destinacija_id = obvezen_atribut(element, "destinacijaId")
        if destinacija_id not in destinacije:
            raise NapakaPodatkov(f"Potovanje {ident} se sklicuje na neobstoječo destinacijo {destinacija_id}.")
        odhod = datum_polja(element, "datumOdhoda")
        vrnitev = datum_polja(element, "datumVrnitve")
        if preveri_datum(vrnitev) < preveri_datum(odhod):
            raise NapakaPodatkov(f"Potovanje {ident}: datum vrnitve je pred datumom odhoda.")
        tip = besedilo(element, "tipPrtljage")
        if tip not in DOVOLJENA_PRTLJAGA:
            raise NapakaPodatkov(f"Potovanje {ident}: neznana vrsta prtljage '{tip}'.")
        seznam = element.find("aktivnosti")
        if seznam is None or not seznam.findall("aktivnostRef"):
            raise NapakaPodatkov(f"Potovanje {ident} mora vsebovati vsaj eno izbrano aktivnost.")
        izbrane = []
        videni = set()
        for referenca in seznam.findall("aktivnostRef"):
            aktivnost_id = obvezen_atribut(referenca, "id")
            if aktivnost_id not in aktivnosti:
                raise NapakaPodatkov(f"Potovanje {ident} se sklicuje na neobstoječo aktivnost {aktivnost_id}.")
            if aktivnost_id in videni:
                raise NapakaPodatkov(f"Potovanje {ident}: aktivnost {aktivnost_id} je navedena dvakrat.")
            videni.add(aktivnost_id)
            aktivnost = aktivnosti[aktivnost_id]
            if aktivnost["destinacija_id"] != destinacija_id:
                raise NapakaPodatkov(f"Potovanje {ident}: aktivnost {aktivnost_id} ne pripada izbrani destinaciji.")
            izbrane.append(aktivnost.copy())
        zapis = {
            "id": ident,
            "destinacija": destinacije[destinacija_id].copy(),
            "datum_odhoda": odhod,
            "datum_vrnitve": vrnitev,
            "tip_prtljage": tip,
            "max_teza": stevilo(element, "maxTeza", pozitivno=True),
            "aktivnosti": izbrane,
        }
        dodaj_unikaten(potovanja, zapis, "potovanja.xml")
    return list(potovanja.values())


def filtriraj_potovanja(potovanja, od_datuma=None, destinacija=None, tip_prtljage=None):
    """Za prikaz in oba izvoza uporabi povsem isti seznam rezultatov."""
    if od_datuma is not None and isinstance(od_datuma, str):
        od_datuma = preveri_datum(od_datuma)
    if destinacija is not None:
        iskana = destinacija.strip().casefold()
        znane = {p["destinacija"]["id"].casefold() for p in potovanja}
        znane.update(p["destinacija"]["naziv"].casefold() for p in potovanja)
        if iskana not in znane:
            raise ValueError(f"Neznana destinacija '{destinacija}'. Uporabite naziv ali ID iz podatkov.")
    if tip_prtljage is not None and tip_prtljage not in DOVOLJENA_PRTLJAGA:
        raise ValueError(f"Neznana vrsta prtljage '{tip_prtljage}'. Možnosti: {', '.join(sorted(DOVOLJENA_PRTLJAGA))}.")

    rezultati = []
    for potovanje in potovanja:
        kraj = potovanje["destinacija"]
        if od_datuma and preveri_datum(potovanje["datum_odhoda"]) < od_datuma:
            continue
        if destinacija and iskana not in {kraj["id"].casefold(), kraj["naziv"].casefold()}:
            continue
        if tip_prtljage and potovanje["tip_prtljage"] != tip_prtljage:
            continue
        rezultati.append(potovanje)
    return rezultati


def izpisi_rezultate(potovanja):
    if not potovanja:
        print("Nobeno potovanje ne ustreza izbranim filtrom.")
    else:
        print(f"Najdenih potovanj: {len(potovanja)}")
    for zapis in potovanja:
        print(f"\n{zapis['id']} | {zapis['destinacija']['naziv']}")
        print(f"  Odhod: {zapis['datum_odhoda']} | Vrnitev: {zapis['datum_vrnitve']}")
        print(f"  Prtljaga: {zapis['tip_prtljage']} | Največja teža: {zapis['max_teza']:g} kg")
        print("  Aktivnosti: " + ", ".join(a["naziv"] for a in zapis["aktivnosti"]))


def izvozi_json(potovanja, pot):
    with Path(pot).open("w", encoding="utf-8") as datoteka:
        json.dump({"potovanja": potovanja}, datoteka, ensure_ascii=False, indent=4)
        datoteka.write("\n")


def dodaj_besedilo(nadrejeni, oznaka, vrednost):
    polje = ET.SubElement(nadrejeni, oznaka)
    if vrednost is not None:
        polje.text = str(vrednost)
    return polje


def izvozi_xml(potovanja, pot):
    """Sestavi nov XML iz že povezanih in filtriranih slovarjev, ne iz vhodnih datotek."""
    koren = ET.Element("filtriranaPotovanja")
    for zapis in potovanja:
        el_pot = ET.SubElement(koren, "potovanje", {"id": zapis["id"]})
        kraj = zapis["destinacija"]
        el_kraj = ET.SubElement(el_pot, "destinacija", {"id": kraj["id"]})
        for oznaka, kljuc in (
            ("naziv", "naziv"), ("drzava", "drzava"),
            ("povprecnaTemperatura", "povprecna_temperatura"),
            ("opis", "opis"), ("datumZadnjegaObiska", "datum_zadnjega_obiska"),
        ):
            dodaj_besedilo(el_kraj, oznaka, kraj[kljuc])
        for oznaka, kljuc in (
            ("datumOdhoda", "datum_odhoda"), ("datumVrnitve", "datum_vrnitve"),
            ("tipPrtljage", "tip_prtljage"), ("maxTeza", "max_teza"),
        ):
            dodaj_besedilo(el_pot, oznaka, zapis[kljuc])
        el_aktivnosti = ET.SubElement(el_pot, "aktivnosti")
        for aktivnost in zapis["aktivnosti"]:
            el_a = ET.SubElement(el_aktivnosti, "aktivnost", {
                "id": aktivnost["id"], "destinacijaId": aktivnost["destinacija_id"]
            })
            for oznaka, kljuc in (
                ("naziv", "naziv"), ("kategorija", "kategorija"),
                ("trajanjeUr", "trajanje_ur"), ("opis", "opis"),
            ):
                dodaj_besedilo(el_a, oznaka, aktivnost[kljuc])
    ET.indent(koren, space="    ")
    ET.ElementTree(koren).write(pot, encoding="utf-8", xml_declaration=True)


def main(argv=None):
    parser = SlovenskiParser(description="SmartPack: filtriranje potovanj iz datotek XML.", add_help=False)
    parser.add_argument("-h", "--help", action="help", help="Prikaži pomoč in zaključi program.")
    parser.add_argument("--od-datuma", type=datum_argument, metavar="YYYY-MM-DD", help="Prikaži odhode od vključno tega dne.")
    parser.add_argument("--destinacija", help="Naziv ali ID destinacije (npr. Barcelona ali D001).")
    parser.add_argument("--tip-prtljage", help="Vrsta prtljage: rocna, oddana ali nahrbtnik.")
    argumenti = parser.parse_args(argv)
    try:
        potovanja = nalozi_podatke()
        rezultati = filtriraj_potovanja(potovanja, argumenti.od_datuma, argumenti.destinacija, argumenti.tip_prtljage)
        izpisi_rezultate(rezultati)
        izvozi_json(rezultati, MAPA_PROJEKTA / "filtrirano.json")
        izvozi_xml(rezultati, MAPA_PROJEKTA / "filtrirano.xml")
    except ValueError as napaka:
        parser.error(str(napaka))
    except (NapakaPodatkov, OSError) as napaka:
        print(f"Napaka: {napaka}", file=sys.stderr)
        return 1
    print("\nUstvarjeni datoteki: filtrirano.json in filtrirano.xml")
    return 0


if __name__ == "__main__":
    sys.exit(main())

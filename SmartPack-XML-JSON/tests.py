"""Samodejni preizkusi za nalogo SmartPack – XML in JSON."""

import contextlib
from datetime import date
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import main


PROJEKT = Path(__file__).resolve().parent
PODATKI = PROJEKT / "data"


class PreizkusiSmartPack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.potovanja = main.nalozi_podatke()

    def zacasni_podatki(self):
        zacasna = tempfile.TemporaryDirectory()
        mapa = Path(zacasna.name) / "data"
        shutil.copytree(PODATKI, mapa)
        self.addCleanup(zacasna.cleanup)
        return mapa

    def spremeni_xml(self, mapa, datoteka, sprememba):
        pot = mapa / datoteka
        drevo = ET.parse(pot)
        sprememba(drevo.getroot())
        drevo.write(pot, encoding="utf-8", xml_declaration=True)

    def zaganjaj(self, *argumenti, cwd=None):
        return subprocess.run(
            [sys.executable, str(PROJEKT / "main.py"), *argumenti],
            cwd=cwd or PROJEKT, capture_output=True, text=True, check=False,
        )

    def xml_v_slovarje(self, pot):
        """Neodvisno preberi izvoženi XML in sestavi isto vsebino kot v JSON."""
        koren = ET.parse(pot).getroot()
        self.assertEqual(koren.tag, "filtriranaPotovanja")

        def polje(element, oznaka):
            vsebina = element.find(oznaka)
            self.assertIsNotNone(vsebina)
            return vsebina.text if vsebina.text else None

        rezultati = []
        for el_p in koren.findall("potovanje"):
            el_d = el_p.find("destinacija")
            self.assertIsNotNone(el_d)
            kraj = {
                "id": el_d.attrib["id"],
                "naziv": polje(el_d, "naziv"),
                "drzava": polje(el_d, "drzava"),
                "povprecna_temperatura": int(polje(el_d, "povprecnaTemperatura")),
                "opis": polje(el_d, "opis"),
                "datum_zadnjega_obiska": polje(el_d, "datumZadnjegaObiska"),
            }
            aktivnosti = []
            for el_a in el_p.findall("./aktivnosti/aktivnost"):
                aktivnosti.append({
                    "id": el_a.attrib["id"],
                    "destinacija_id": el_a.attrib["destinacijaId"],
                    "naziv": polje(el_a, "naziv"),
                    "kategorija": polje(el_a, "kategorija"),
                    "trajanje_ur": int(polje(el_a, "trajanjeUr")),
                    "opis": polje(el_a, "opis"),
                })
            rezultati.append({
                "id": el_p.attrib["id"],
                "destinacija": kraj,
                "datum_odhoda": polje(el_p, "datumOdhoda"),
                "datum_vrnitve": polje(el_p, "datumVrnitve"),
                "tip_prtljage": polje(el_p, "tipPrtljage"),
                "max_teza": float(polje(el_p, "maxTeza")),
                "aktivnosti": aktivnosti,
            })
        return rezultati

    def test_tri_datoteke_so_berljive_in_pravilni_koreni(self):
        for ime, oznaka in (
            ("destinacije.xml", "destinacije"),
            ("aktivnosti.xml", "aktivnosti"),
            ("potovanja.xml", "potovanja"),
        ):
            with self.subTest(datoteka=ime):
                self.assertEqual(ET.parse(PODATKI / ime).getroot().tag, oznaka)

    def test_stevilo_glavnih_zapisov(self):
        for ime, oznaka in (
            ("destinacije.xml", "destinacija"),
            ("aktivnosti.xml", "aktivnost"),
            ("potovanja.xml", "potovanje"),
        ):
            with self.subTest(datoteka=ime):
                zapisi = ET.parse(PODATKI / ime).getroot().findall(oznaka)
                self.assertGreaterEqual(len(zapisi), 10)
                self.assertLessEqual(len(zapisi), 15)
        self.assertEqual(len(self.potovanja), 15)

    def test_unikatni_id_v_vseh_datotekah(self):
        for ime in ("destinacije.xml", "aktivnosti.xml", "potovanja.xml"):
            zapisi = list(ET.parse(PODATKI / ime).getroot())
            identifikatorji = [el.attrib["id"] for el in zapisi]
            self.assertEqual(len(identifikatorji), len(set(identifikatorji)))

    def test_id_reference_in_pripadnost_aktivnosti(self):
        kraji = {el.attrib["id"] for el in ET.parse(PODATKI / "destinacije.xml").getroot()}
        aktivnosti = {
            el.attrib["id"]: el.attrib["destinacijaId"]
            for el in ET.parse(PODATKI / "aktivnosti.xml").getroot()
        }
        self.assertTrue(all(dest in kraji for dest in aktivnosti.values()))
        for pot in ET.parse(PODATKI / "potovanja.xml").getroot():
            kraj_id = pot.attrib["destinacijaId"]
            self.assertIn(kraj_id, kraji)
            for ref in pot.findall("./aktivnosti/aktivnostRef"):
                self.assertIn(ref.attrib["id"], aktivnosti)
                self.assertEqual(aktivnosti[ref.attrib["id"]], kraj_id)

    def test_veljavni_datumi_in_kronologija(self):
        for pot in self.potovanja:
            odhod = main.preveri_datum(pot["datum_odhoda"])
            vrnitev = main.preveri_datum(pot["datum_vrnitve"])
            self.assertLessEqual(odhod, vrnitev)
            kraj_datum = pot["destinacija"]["datum_zadnjega_obiska"]
            if kraj_datum:
                main.preveri_datum(kraj_datum)

    def test_prazna_opcijska_polja_so_none(self):
        barcelona = next(p for p in self.potovanja if p["destinacija"]["id"] == "D001")
        edinburgh = next(p for p in self.potovanja if p["destinacija"]["id"] == "D012")
        self.assertIsNone(barcelona["destinacija"]["datum_zadnjega_obiska"])
        self.assertIsNone(edinburgh["destinacija"]["opis"])

    def test_stevila_so_ustreznega_tipa(self):
        for pot in self.potovanja:
            self.assertIsInstance(pot["max_teza"], float)
            self.assertIsInstance(pot["destinacija"]["povprecna_temperatura"], int)
            for aktivnost in pot["aktivnosti"]:
                self.assertIsInstance(aktivnost["trajanje_ur"], int)

    def test_filtriranje_po_datumu(self):
        meja = date(2027, 1, 1)
        izbrana = main.filtriraj_potovanja(self.potovanja, od_datuma=meja)
        self.assertTrue(izbrana)
        self.assertTrue(all(main.preveri_datum(p["datum_odhoda"]) >= meja for p in izbrana))
        self.assertTrue(any(main.preveri_datum(p["datum_odhoda"]) < meja for p in self.potovanja))

    def test_filtriranje_po_destinaciji_ime_in_id(self):
        po_imenu = main.filtriraj_potovanja(self.potovanja, destinacija="  barcelona ")
        po_id = main.filtriraj_potovanja(self.potovanja, destinacija="d001")
        self.assertEqual([p["id"] for p in po_imenu], ["P001", "P013"])
        self.assertEqual(po_imenu, po_id)

    def test_filtriranje_po_prtljagi(self):
        izbrana = main.filtriraj_potovanja(self.potovanja, tip_prtljage="rocna")
        self.assertTrue(izbrana)
        self.assertTrue(all(p["tip_prtljage"] == "rocna" for p in izbrana))

    def test_kombinirani_filtri(self):
        izbrana = main.filtriraj_potovanja(
            self.potovanja, od_datuma=date(2027, 1, 1),
            destinacija="Barcelona", tip_prtljage="oddana",
        )
        self.assertEqual([p["id"] for p in izbrana], ["P013"])

    def test_filtri_brez_ujemanj(self):
        self.assertEqual(main.filtriraj_potovanja(self.potovanja, od_datuma=date(2035, 1, 1)), [])
        self.assertEqual(main.filtriraj_potovanja(self.potovanja, destinacija="Barcelona", tip_prtljage="nahrbtnik"), [])

    def test_neznani_filtri_in_nepravilni_datumi(self):
        for niz in ("2026-02-30", "2026-2-03", "napačen datum"):
            with self.subTest(vrednost=niz), self.assertRaises(ValueError):
                main.preveri_datum(niz)
        with self.assertRaisesRegex(ValueError, "Neznana destinacija"):
            main.filtriraj_potovanja(self.potovanja, destinacija="Neobstoječe mesto")
        with self.assertRaisesRegex(ValueError, "Neznana vrsta"):
            main.filtriraj_potovanja(self.potovanja, tip_prtljage="kovcek")

    def test_izvoz_json_xml_in_enaka_vsebina(self):
        primeri = [
            self.potovanja,
            main.filtriraj_potovanja(self.potovanja, destinacija="Barcelona"),
            main.filtriraj_potovanja(self.potovanja, destinacija="Barcelona", tip_prtljage="nahrbtnik"),
        ]
        with tempfile.TemporaryDirectory() as zacasna:
            for filtrirana in primeri:
                with self.subTest(stevilo=len(filtrirana)):
                    json_pot, xml_pot = Path(zacasna) / "rezultat.json", Path(zacasna) / "rezultat.xml"
                    main.izvozi_json(filtrirana, json_pot)
                    main.izvozi_xml(filtrirana, xml_pot)
                    zapis = json.loads(json_pot.read_text(encoding="utf-8"))
                    self.assertEqual(zapis["potovanja"], filtrirana)
                    self.assertEqual(zapis, {"potovanja": self.xml_v_slovarje(xml_pot)})
                    self.assertIn(b"encoding='utf-8'", xml_pot.read_bytes().lower())
                    if any(p["destinacija"]["id"] == "D001" for p in filtrirana):
                        self.assertIn("Gaudí", json_pot.read_text(encoding="utf-8"))

    def test_manjkajoca_datoteka(self):
        mapa = self.zacasni_podatki()
        (mapa / "potovanja.xml").unlink()
        with self.assertRaisesRegex(main.NapakaPodatkov, "ne obstaja"):
            main.nalozi_podatke(mapa)

    def test_nepravilna_xml_sintaksa(self):
        mapa = self.zacasni_podatki()
        (mapa / "aktivnosti.xml").write_text("<aktivnosti><aktivnost>", encoding="utf-8")
        with self.assertRaisesRegex(main.NapakaPodatkov, "ni veljaven XML"):
            main.nalozi_podatke(mapa)

    def test_napacen_korenski_element(self):
        mapa = self.zacasni_podatki()
        (mapa / "destinacije.xml").write_text("<napacen />", encoding="utf-8")
        with self.assertRaisesRegex(main.NapakaPodatkov, "korenski element"):
            main.nalozi_podatke(mapa)

    def test_manjkajoce_obvezno_polje(self):
        mapa = self.zacasni_podatki()
        self.spremeni_xml(mapa, "destinacije.xml", lambda root: root[0].remove(root[0].find("naziv")))
        with self.assertRaisesRegex(main.NapakaPodatkov, "manjka obvezno polje"):
            main.nalozi_podatke(mapa)

    def test_podvojen_id(self):
        mapa = self.zacasni_podatki()
        self.spremeni_xml(mapa, "destinacije.xml", lambda root: root[1].set("id", root[0].get("id")))
        with self.assertRaisesRegex(main.NapakaPodatkov, "Podvojen ID"):
            main.nalozi_podatke(mapa)

    def test_neobstojeca_destinacija_v_aktivnosti(self):
        mapa = self.zacasni_podatki()
        self.spremeni_xml(mapa, "aktivnosti.xml", lambda root: root[0].set("destinacijaId", "D999"))
        with self.assertRaisesRegex(main.NapakaPodatkov, "neobstoječo destinacijo"):
            main.nalozi_podatke(mapa)

    def test_neobstojeca_destinacija_v_potovanju(self):
        mapa = self.zacasni_podatki()
        self.spremeni_xml(mapa, "potovanja.xml", lambda root: root[0].set("destinacijaId", "D999"))
        with self.assertRaisesRegex(main.NapakaPodatkov, "neobstoječo destinacijo"):
            main.nalozi_podatke(mapa)

    def test_neobstojeca_aktivnost_v_potovanju(self):
        mapa = self.zacasni_podatki()
        self.spremeni_xml(mapa, "potovanja.xml", lambda root: root[0].find("./aktivnosti/aktivnostRef").set("id", "A999"))
        with self.assertRaisesRegex(main.NapakaPodatkov, "neobstoječo aktivnost"):
            main.nalozi_podatke(mapa)

    def test_aktivnost_iz_napacne_destinacije(self):
        mapa = self.zacasni_podatki()
        self.spremeni_xml(mapa, "potovanja.xml", lambda root: root[0].find("./aktivnosti/aktivnostRef").set("id", "A003"))
        with self.assertRaisesRegex(main.NapakaPodatkov, "ne pripada izbrani destinaciji"):
            main.nalozi_podatke(mapa)

    def test_neveljaven_datum_v_datoteki(self):
        mapa = self.zacasni_podatki()
        self.spremeni_xml(mapa, "potovanja.xml", lambda root: setattr(root[0].find("datumOdhoda"), "text", "2026-02-30"))
        with self.assertRaisesRegex(main.NapakaPodatkov, "ne obstaja"):
            main.nalozi_podatke(mapa)

    def test_vrnitev_pred_odhodom(self):
        mapa = self.zacasni_podatki()
        self.spremeni_xml(mapa, "potovanja.xml", lambda root: setattr(root[0].find("datumVrnitve"), "text", "2026-01-01"))
        with self.assertRaisesRegex(main.NapakaPodatkov, "pred datumom odhoda"):
            main.nalozi_podatke(mapa)

    def test_neveljavno_stevilo(self):
        mapa = self.zacasni_podatki()
        self.spremeni_xml(mapa, "potovanja.xml", lambda root: setattr(root[0].find("maxTeza"), "text", "osem"))
        with self.assertRaisesRegex(main.NapakaPodatkov, "ni veljavno število"):
            main.nalozi_podatke(mapa)

    def test_zagon_brez_argumentov_in_iz_druge_mape(self):
        with tempfile.TemporaryDirectory() as druga_mapa:
            proces = self.zaganjaj(cwd=druga_mapa)
        self.assertEqual(proces.returncode, 0, proces.stderr)
        self.assertIn("Najdenih potovanj: 15", proces.stdout)
        json_pot = PROJEKT / "filtrirano.json"
        self.assertEqual(len(json.loads(json_pot.read_text(encoding="utf-8"))["potovanja"]), 15)

    def test_napaka_cli_ne_izpise_traceback(self):
        for argumenti in (
            ("--od-datuma", "2026-02-30"),
            ("--destinacija", "Neobstoječe mesto"),
            ("--tip-prtljage", "neznana"),
        ):
            with self.subTest(argumenti=argumenti):
                proces = self.zaganjaj(*argumenti)
                self.assertNotEqual(proces.returncode, 0)
                self.assertNotIn("Traceback", proces.stderr)
                self.assertTrue(proces.stderr.strip())

    def test_cli_manjkajoca_datoteka_brez_tracebacka(self):
        with mock.patch.object(main, "nalozi_podatke", side_effect=main.NapakaPodatkov("Vhodna datoteka ne obstaja.")):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                izhod = main.main([])
            self.assertEqual(izhod, 1)
            self.assertIn("Napaka:", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_primeri_ukazov_in_ponovni_zagon(self):
        ukazi = (
            (), ("--od-datuma", "2026-11-01"), ("--destinacija", "Barcelona"),
            ("--tip-prtljage", "rocna"),
            ("--destinacija", "Barcelona", "--tip-prtljage", "rocna"),
        )
        for argumenti in ukazi:
            with self.subTest(argumenti=argumenti):
                proces = self.zaganjaj(*argumenti)
                self.assertEqual(proces.returncode, 0, proces.stderr)
                self.assertEqual(
                    json.loads((PROJEKT / "filtrirano.json").read_text(encoding="utf-8")),
                    {"potovanja": self.xml_v_slovarje(PROJEKT / "filtrirano.xml")},
                )
        proces = self.zaganjaj("--destinacija", "Barcelona", "--tip-prtljage", "nahrbtnik")
        self.assertEqual(proces.returncode, 0, proces.stderr)
        self.assertIn("Nobeno potovanje", proces.stdout)
        self.assertEqual(json.loads((PROJEKT / "filtrirano.json").read_text(encoding="utf-8")), {"potovanja": []})
        self.assertEqual(self.xml_v_slovarje(PROJEKT / "filtrirano.xml"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

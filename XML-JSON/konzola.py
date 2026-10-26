"""SmartPack: interaktivna konzola (zaženite z `python konzola.py`)."""

import cmd
import shlex
import sys

import main


class KonzolaSmartPack(cmd.Cmd):
    intro = ("SmartPack konzola. Vpišite 'help' za seznam ukazov, 'izhod' za konec.\n"
             "Podatki so naloženi enkrat; ukaze lahko poljubno ponavljate.")
    prompt = "smartpack> "

    def __init__(self, potovanja):
        super().__init__()
        self.potovanja = potovanja

    def _parser(self):
        parser = main.SlovenskiParser(prog="potovanja", add_help=False)
        parser.add_argument("-h", "--help", action="help", help="Prikaži pomoč.")
        parser.add_argument("--od-datuma", type=main.datum_argument, metavar="YYYY-MM-DD")
        parser.add_argument("--destinacija")
        parser.add_argument("--tip-prtljage")
        return parser

    def do_potovanja(self, vrstica):
        """potovanja [--od-datuma YYYY-MM-DD] [--destinacija X] [--tip-prtljage Y]
Izpiše filtrirana potovanja in prepiše filtrirano.json ter filtrirano.xml."""
        try:
            args = self._parser().parse_args(shlex.split(vrstica))
        except SystemExit:
            return
        except ValueError as napaka:
            print(f"Napaka: {napaka}")
            return
        try:
            rezultati = main.filtriraj_potovanja(
                self.potovanja, args.od_datuma, args.destinacija, args.tip_prtljage)
            main.izpisi_rezultate(rezultati)
            main.izvozi_json(rezultati, main.MAPA_PROJEKTA / "filtrirano.json")
            main.izvozi_xml(rezultati, main.MAPA_PROJEKTA / "filtrirano.xml")
        except (ValueError, OSError) as napaka:
            print(f"Napaka: {napaka}")
            return
        print("\nUstvarjeni datoteki: filtrirano.json in filtrirano.xml")

    def do_destinacije(self, _):
        """destinacije
Izpiše destinacije, ki se pojavljajo v potovanjih."""
        videne = {}
        for p in self.potovanja:
            videne[p["destinacija"]["id"]] = p["destinacija"]
        for d in sorted(videne.values(), key=lambda d: d["id"]):
            print(f"{d['id']} | {d['naziv']}, {d['drzava']} | {d['povprecna_temperatura']} °C")

    def do_ponovno_nalozi(self, _):
        """ponovno_nalozi
Ponovno prebere XML-datoteke iz mape data/."""
        try:
            self.potovanja = main.nalozi_podatke()
            print(f"Naloženih potovanj: {len(self.potovanja)}")
        except main.NapakaPodatkov as napaka:
            print(f"Napaka: {napaka}")

    def do_izhod(self, _):
        """izhod
Zapre konzolo."""
        return True

    do_exit = do_quit = do_EOF = do_izhod

    def emptyline(self):
        pass

    def default(self, vrstica):
        print(f"Neznan ukaz: {vrstica.split()[0]}. Vpišite 'help'.")


def zagon():
    try:
        potovanja = main.nalozi_podatke()
    except main.NapakaPodatkov as napaka:
        print(f"Napaka: {napaka}", file=sys.stderr)
        return 1
    try:
        KonzolaSmartPack(potovanja).cmdloop()
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(zagon())

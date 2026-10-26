# SmartPack – Naloga 1: XML in JSON

## Kratek opis

SmartPack je zamisel za pomočnika pri pripravi prtljage. Uporabnik izbere destinacijo, datum potovanja, vrsto prtljage in načrtovane aktivnosti. Pri večjem projektu sta predvidena tudi vremenska napoved Open-Meteo in iskanje zanimivosti z Geoapify. **Ta naloga je manjša, samostojna vaja:** uporablja le lokalne podatke XML, brez spletnih zahtev in brez izdelave celotne spletne aplikacije.

Cilj naloge je prebrati tri povezane datoteke XML, preveriti podatke, jih pretvoriti v Pythonove slovarje in sezname, omogočiti filtriranje potovanj ter iz istih rezultatov izdelati novi datoteki JSON in XML.

## Vhodni podatki in povezave

V mapi `data/` so tri datoteke:

| Datoteka | Število zapisov | Vsebina |
|---|---:|---|
| `destinacije.xml` | 12 | ID destinacije, naziv, država, povprečna temperatura, opis in neobvezen datum zadnjega obiska. |
| `aktivnosti.xml` | 15 | ID aktivnosti, `destinacijaId`, naziv, kategorija, trajanje v urah in opis. |
| `potovanja.xml` | 15 | ID potovanja, `destinacijaId`, datuma odhoda in vrnitve, tip prtljage, največja teža ter izbrane aktivnosti. |

Vsak glavni zapis ima svoj unikaten atribut `id`. Povezave so narejene **prek ID-jev**, ne prek vrstnega reda ali imen:

- `aktivnost.destinacijaId` kaže na `destinacija.id`;
- `potovanje.destinacijaId` kaže na `destinacija.id`;
- `potovanje/aktivnosti/aktivnostRef.id` kaže na `aktivnost.id`.

Program preveri, da reference obstajajo in da izbrane aktivnosti res pripadajo destinaciji potovanja. Poleg tega preveri obvezna polja, števila, veljavnost datumov in vrstni red odhoda ter vrnitve. Primer praznega podatka je `datumZadnjegaObiska` pri Barceloni; po branju v Python postane `None`, v JSON pa `null`.

## Tehnologije

Uporabljen je **Python 3.11 ali novejši**, brez dodatnih paketov. Glavne knjižnice so `xml.etree.ElementTree`, `json`, `datetime`, `pathlib`, `argparse` in `unittest`. Program deluje na Windows, Linux in macOS, če je nameščen ustrezen Python.

## Struktura projekta

```text
SmartPack-XML-JSON/
├── data/
│   ├── destinacije.xml
│   ├── aktivnosti.xml
│   └── potovanja.xml
├── main.py
├── tests.py
├── README.md
├── filtrirano.json
└── filtrirano.xml
```

## Zagon in primeri uporabe

Odprite terminal v mapi `SmartPack-XML-JSON` in zaženite:

```bash
python main.py
```

Brez argumentov se izpiše vseh 15 potovanj. Posamezne filtre lahko uporabite samostojno ali skupaj:

```bash
# Odhodi od izbranega datuma (vključno s tem datumom)
python main.py --od-datuma 2026-11-01

# Destinacija po nazivu (neobčutljivo za velike in male črke) ali po ID-ju
python main.py --destinacija Barcelona
python main.py --destinacija D001

# Vrsta prtljage: rocna, oddana ali nahrbtnik
python main.py --tip-prtljage rocna

# Kombinacija filtrov
python main.py --destinacija Barcelona --tip-prtljage rocna
python main.py --od-datuma 2027-01-01 --destinacija Barcelona --tip-prtljage oddana

# Pomoč
python main.py --help
```

Na nekaterih računalnikih je treba namesto `python` uporabiti `python3` ali na Windows `py`. Pri datumih uporabite obliko `YYYY-MM-DD`. Neznana destinacija, neveljaven datum ali napačna vrsta prtljage sproži razumljivo sporočilo o napaki.

Program lahko zaženete tudi iz druge delovne mape, saj poišče podatke glede na lokacijo datoteke `main.py`.

### Interaktivna konzola

Za delo brez ponavljanja zagona zaženite `python konzola.py`. Podatki se naložijo enkrat, nato vpisujete ukaze:

```text
smartpack> potovanja --destinacija Barcelona --tip-prtljage rocna
smartpack> destinacije
smartpack> ponovno_nalozi
smartpack> help
smartpack> izhod
```

Ukaz `potovanja` sprejme iste filtre kot `main.py` in prav tako prepiše `filtrirano.json` ter `filtrirano.xml`.

## Rezultati: JSON in XML

Ob vsakem uspešnem zagonu se v mapi projekta ustvarita oziroma prepišeta:

- **`filtrirano.json`** – vsebuje objekt s seznamom `potovanja`. Vsako potovanje vključuje podatke svoje destinacije in izbranih aktivnosti. Števila ostanejo števila, manjkajoče neobvezne vrednosti so `null`.
- **`filtrirano.xml`** – na novo ustvarjeni dokument s korenom `<filtriranaPotovanja>`, povezanimi podatki o destinaciji ter elementi aktivnosti. Ne gre za kopijo vhodnih XML-datotek.

Oba izvoza nastaneta iz **istega filtriranega seznama Pythonovih slovarjev**, zato sta vsebinsko usklajena. Datoteki uporabljata UTF-8 in pregledno oblikovanje. Primeroma priložena izvoza v tem ZIP-u sta ustvarjena z ukazom `python main.py --destinacija Barcelona` (potovanji P001 in P013).

Če nobeno potovanje ne ustreza filtrom, se izpiše obvestilo, JSON vsebuje `{"potovanja": []}`, XML pa prazen korenski element `<filtriranaPotovanja />`. Prejšnji rezultati se ob uspešnem zagonu vedno prepišejo.

## Preizkusi

Iz mape projekta zaženite:

```bash
python tests.py
```

Datoteka vsebuje 30 samodejnih preizkusov, med drugim:

- branje vseh XML-datotek, pravilne korene, število zapisov in unikatne ID-je;
- pravilnost vseh referenc ter pripadnost aktivnosti destinaciji;
- datume, numerična polja in prazne neobvezne vrednosti;
- posamične in kombinirane filtre ter primer brez zadetkov;
- zavrnitev poškodovanih podatkov (manjkajoča datoteka ali polje, neveljaven XML, podvojeni ID, napačna referenca, datum in število);
- zagon iz druge mape, neveljavne argumente in več zaporednih zagonov;
- veljavnost izvoženih formatov ter **vsebinsko primerjavo** podatkov po ponovnem branju JSON in XML.

Preizkusi programa med izvajanjem lahko prepišejo izhodni datoteki. Za ponovno ustvarjanje priloženega primera po testiranju zaženite:

```bash
python main.py --destinacija Barcelona
```

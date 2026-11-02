# SmartPack – Naloga 3: Odprti podatki

Samostojna aplikacija Streamlit za pregled turistične statistike Slovenije.
Prikazuje **Top 10 občin po številu prihodov turistov** za izbrani mesec in leto
(tekoče leto ter največ šest prejšnjih let) in **mesečne prihode** za izbrano občino. Na lestvici je mogoče preklopiti
med grafom in seznamom; na črtnem grafu lahko vključite primerjavo dveh občin.

## Vir podatkov

- [OPSI: Prihodi in prenočitve turistov po državah, občine, Slovenija, mesečno](https://podatki.gov.si/dataset/surs2164466s)
- Statistični urad Republike Slovenije (SURS), tabela **2164466S**.
- Izvorni format: **PC-Axis (.PX)**, licenca **CC BY 4.0** (navedba vira).
- Neposredni vir: `https://pxweb.stat.si/SiStatData/Resources/PX/Databases/Data/2164466S.PX`

Program ob odprtju samodejno prenese izvirno datoteko `.PX`, prebere metapodatke
`STUB`, `HEADING`, `VALUES` in `DATA` ter izbere samo meritev **Prihodi turistov**
in državo izvora **0 Država - SKUPAJ** (domači + tuji). Državnega seštevka
**SLOVENIJA** ne šteje med občine. Manjkajočih podatkov ne prikazuje kot nič.

## Namestitev in zagon

Potrebujete Python 3.10 ali novejši in internetno povezavo.

```bash
cd Open-Data
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Aplikacija se odpre v spletnem brskalniku. Izberite leto in mesec za lestvico
Top 10 ter s stikalom **Prikaži seznam namesto grafa** izberite prikaz.
Pri mesečnem grafu izberite občino, pod grafom vključite
**Primerjaj z drugo občino** in izberite drugo občino. Graf prikaže obe
časovni vrsti na isti osi za izbrano leto. Izbira druge občine ostane
nespremenjena, ko zamenjate prvo občino (razen če bi bili obe enaki).
Za ročno ponovno pridobivanje podatkov kliknite **Osveži podatke s SURS**.
Podatki se sicer hranijo v predpomnilniku za največ eno uro, nato se ponovno
prenesejo ob naslednji uporabi aplikacije. Ne uporabljamo vnaprej pripravljenih
CSV/JSON rezultatov.

## Testiranje

```bash
python -m unittest discover -s tests -v
```

Testi preverjajo branje PC-Axis, pravilno izbiro skupnih prihodov, razvrščanje,
filtriranje, manjkajoče podatke, primerjavo občin in obdobje šestih preteklih let. Za dejanski
prenos podatkov potrebujete omrežni dostop do `pxweb.stat.si`.

## Povezava s SmartPack

Statistika prikazuje priljubljenost slovenskih destinacij in sezonskost obiska.
V kasnejši različici SmartPack lahko te informacije dopolnijo načrtovanje
potovanja; vreme (Open-Meteo) in znamenitosti (Geoapify) niso del te naloge.

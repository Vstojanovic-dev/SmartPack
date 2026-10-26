# SmartPack – Naloga 2: Parser

Samostojen razčlenjevalnik v Pythonu pridobi **HTML** članka [Wikivoyage: Packing list](https://en.wikivoyage.org/wiki/Packing_list) ter iz njega izlušči priporočila za pakiranje. Podatke shrani v `data/packing_data.json` za poznejšo uporabo v aplikaciji SmartPack. Wikivoyage API-ja ne uporablja; integraciji z Open-Meteo in Geoapify nista del te naloge.

## Namestitev in zagon

Potrebujete Python 3.9+ in internetno povezavo. Uporabljene knjižnice so `requests`, `beautifulsoup4` ter standardni moduli Python (`json`, `pathlib` itd.). V mapi projekta zaženite:

```bash
python -m pip install -r requirements.txt
python parser.py
```

Program vpraša za kontakt za identifikacijo svojega **User-Agent** (vaš e-poštni naslov ali javni URL vašega repozitorija), kot ga zahteva Wikimedia. Lahko ga nastavite tudi vnaprej (zamenjajte primer z resničnim kontaktom):

```powershell
# Windows PowerShell
$env:SMARTPACK_CONTACT = "https://github.com/vas-uporabnik/SmartPack-Parser"
python parser.py
```

```bash
# macOS / Linux
export SMARTPACK_CONTACT="https://github.com/vas-uporabnik/SmartPack-Parser"
python parser.py
```

## Delovanje

1. `requests` prenese `robots.txt`, preveri dovoljenje in nato z ustreznim User-Agentom, časovno omejitvijo in preverjanjem HTTP statusa prenese **HTML članka**.
2. `BeautifulSoup` iz glavnega dela članka (`#mw-content-text .mw-parser-output`, z nadomestnima izbirnikoma) prebere naslove `h2`–`h4`, sezname `ul`/`ol` s postavkami `li` ter odstavke `p`.
3. Kategorije sestavi iz dejanskih naslovov. Iz seznamov prebere postavke, tudi daljše; iz odstavkov vzame le izrecna, dovolj jasno zapisana priporočila (npr. stavek, ki se začne z »Bring ...«). Splošnih odstavkov ne spreminja v predmete. Odstrani odvečne presledke, prazne in podvojene postavke; izloči navigacijo, sklice, gumbe za urejanje in razdelek »See also«.
4. Ko so podatki uspešno pridobljeni, ustvari in preveri JSON v kodiranju UTF-8. Prejšnjo datoteko zamenja šele po uspešnem zapisu začasne datoteke. Ob neuspehu je ne prepiše.

Izhodna datoteka `data/packing_data.json` vsebuje podatke o viru, čas pridobitve (UTC, ISO-8601) in seznam kategorij z izvornimi angleškimi nazivi predmetov. Mapa `data` se ustvari samodejno; `.gitkeep` omogoča, da je tudi prazna mapa vključena v repozitorij.

Če stran ni dostopna, `robots.txt` ne dovoli branja ali ni prepoznanih priporočil, program javi napako. Zaščit spletnega mesta ne poskuša obiti. Ker je vsebina članka predvsem opisna, rezultat ni nujno popoln seznam vseh predmetov, ki jih članek omenja.

## Preverjanje

```bash
python -m unittest discover -s tests -v
```

Testi uporabljajo ilustrativne lokalne HTML primere in preverjajo tudi zaščito že shranjenega JSON-a. Niso nadomestilo za preverjanje prenosa s prave spletne strani. Za to zaženite `python parser.py` z dejanskim kontaktnim podatkom in preverite izpis ter `data/packing_data.json`.

## Uporaba v SmartPack

Končna aplikacija prebere JSON kot osnovni seznam za pakiranje. Pozneje ga bo lahko prilagodila vremenskim razmeram iz Open-Meteo ter destinaciji in dejavnostim iz Geoapify.

**Vir in pripis:** [Wikivoyage contributors, Packing list](https://en.wikivoyage.org/wiki/Packing_list) ([zgodovina članka](https://en.wikivoyage.org/w/index.php?title=Packing_list&action=history)); [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Pri nadaljnji javni uporabi upoštevajte pogoje licence.

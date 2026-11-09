# SmartPack – Naloga 4

Streamlit vmesnik nad obstoječim projektom SmartPack pripravi prilagojen seznam za pakiranje. Geoapify prepozna destinacijo, Open-Meteo prispeva dejansko dnevno napoved, Gemini pa dinamično ustvari strukturiran JSON. Pydantic ga deserializira in preveri pred prikazom; seznam ni statičen. Označevanje spakiranih predmetov ne pošilja nove zahteve Gemini.

## Namestitev in zagon

Uporabite Python 3.10 ali novejsi. V PowerShell iz korena projekta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
cd LLM
python -m pip install -r requirements.txt
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
```

V `secrets.toml` vpišite prava ključa GEMINI_API_KEY in GEOAPIFY_API_KEY. Ključev nikoli ne dodajajte v Git. Namesto datoteke lahko uporabite okoljske spremenljivke:

```powershell
$env:GEMINI_API_KEY = 'vaš-ključ'
$env:GEOAPIFY_API_KEY = 'vaš-ključ'
$env:GEMINI_MODEL = 'gemini-3.1-flash-lite'
python -m streamlit run app.py
```

Če pravilnik PowerShell blokira aktivacijo okolja, v mapi LLM uporabite `..\.venv\Scripts\python.exe -m pip install -r requirements.txt` in `..\.venv\Scripts\python.exe -m streamlit run app.py`.

GEMINI_MODEL je izbiren; privzeto je `gemini-3.1-flash-lite`. Štiri neposredne odvisnosti so Streamlit, requests, Pydantic in google-genai; httpx je odvisnost SDK. Drugo uporabljeno funkcionalnost zagotavlja standardna knjižnica Python.

## Uporaba in odgovor

Vnesite destinacijo, datum odhoda, trajanje in vrsto prtljage; po zelji vklopite omejitev teze in izberite aktivnosti. Kliknite `Generiraj seznam za pakiranje`. Ob rezultatu preverite prepoznano lokacijo, dejansko pokrito obdobje vremenske napovedi in opozorila o manjkajocih podatkih. Spakirane predmete oznacujte s potrditvenimi polji in spremljajte napredek; to uporablja shranjeni seznam brez nove zahteve LLM. Kategorije so razdeljene v razsirljive skupine s stevilom predmetov; vsaka vrstica prikaze kolicino in en kratek razlog. Dnevno napoved in dodatne nasvete odprite po potrebi. Z gumbom `Prenesi seznam (JSON)` prenesite seznam.

Odgovor ima strukturo `PackingRecommendation(destination, duration_days, luggage_type, categories, general_advice)`, kategorije `PackingCategory(name, items)` in predmete `PackingItem(name, quantity, unit, reason)`. SDK prejme `response_mime_type='application/json'` in `response_json_schema=PackingRecommendation.model_json_schema()`. Dejanski `response.text` nato preveri `PackingRecommendation.model_validate_json(...)` pred prikazom. Validacija zahteva neprazne kategorije in sezname predmetov, strogo pozitivne celostevilske kolicine in brez podvojenih predmetov; preveri se tudi ujemanje s potovanjem. Neveljaven odgovor se zavrne brez nadomestnega seznama.

## Viri in omejitve

Obstoječi `Parser/data/packing_data.json` se prebere glede na lokacijo modula, ne glede na trenutni delovni imenik. Parser se ne zažene samodejno. Če datoteka manjka ali je poškodovana, se generiranje nadaljuje z opozorilom in brez tega vira. Ob rezultatu so navedeni članek Wikivoyage, zgodovina in licenca iz metapodatkov.

Open-Meteo vrača do 16 dni napovedi. Pri daljšem potovanju je prikazano dejansko pokrito obdobje; zunaj obzorja se seznam ustvari brez vremenske napovedi. Napoved je negotova. Seznam ne zagotavlja skupne mase prtljage, skladnosti s pravili letalskega prevoznika ali vizumskih zahtev.

Kvota in obračun Gemini sta vezana na projekt API; naročnina na aplikacijo Gemini ne vključuje samodejno uporabe API. Razpoložljivost modela, brezplačne kvote in cene preverite v uradnih virih: [SDK](https://googleapis.github.io/python-genai/), [modeli](https://ai.google.dev/gemini-api/docs/models), [cene](https://ai.google.dev/gemini-api/docs/pricing), [Geoapify](https://apidocs.geoapify.com/docs/geocoding/forward-geocoding/), [Open-Meteo](https://open-meteo.com/en/docs).

## Preverjanje

Iz mape LLM:

```powershell
python -m unittest discover -s tests -v
```

Vseh 35 testov unittest z nadomeščenimi odgovori storitev je uspešno opravljenih; uspešno je tudi preverjanje sintakse. Testi vmesnika uporabljajo pravi Streamlit AppTest, brez živih zahtev API. Integracija s pravimi storitvami API še ni preverjena; pravi ključi in živi testi API niso bili uporabljeni.

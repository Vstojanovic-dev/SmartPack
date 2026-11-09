"""Streamlit entry point; run from LLM with python -m streamlit run app.py."""
import os
import sys
from importlib.util import find_spec
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
st.set_page_config(page_title='SmartPack', page_icon='🧳')
st.title('SmartPack – AI pomočnik za pakiranje')
st.write('Ustvarite prilagojen seznam stvari za vaše naslednje potovanje s pomočjo umetne inteligence.')

try:
    for dependency in ('pydantic', 'httpx', 'google.genai'):
        try:
            available = find_spec(dependency)
        except ModuleNotFoundError:
            available = None
        if available is None:
            raise ModuleNotFoundError(name=dependency)
    from pydantic import ValidationError
    from LLM.models import TripInput, ServiceError, LUGGAGE_TYPES, ACTIVITIES
    from LLM.geocoding_service import geocode_destination
    from LLM.weather_service import get_weather_forecast
    from LLM.context_service import load_packing_data
    from LLM.llm_service import generate_packing_recommendation, DEFAULT_MODEL
except ModuleNotFoundError as error:
    if error.name not in {'pydantic', 'pydantic_core', 'httpx', 'google', 'google.genai'}:
        raise
    st.error('Manjkajo odvisnosti. V mapi LLM zaženite: python -m pip install -r requirements.txt')
    st.stop()


def setting(name, default=''):
    value = os.environ.get(name)
    if value is None:
        try:
            value = st.secrets.get(name, default)
        except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
            value = default
    return value.strip() if isinstance(value, str) else default


gemini_key = setting('GEMINI_API_KEY')
geo_key = setting('GEOAPIFY_API_KEY')
model = setting('GEMINI_MODEL', DEFAULT_MODEL) or DEFAULT_MODEL
if not gemini_key or not geo_key:
    st.info('Nastavite GEMINI_API_KEY in GEOAPIFY_API_KEY v okolju ali .streamlit/secrets.toml.')

weight_enabled = st.checkbox('Omejitev teže prtljage', key='weight_enabled')
with st.form('trip_form'):
    destination = st.text_input('Destinacija', placeholder='Barcelona, Spain')
    departure = st.date_input('Datum odhoda', min_value=date.today())
    duration = st.number_input('Trajanje potovanja (dni)', min_value=1, max_value=60, value=7, step=1)
    luggage = st.selectbox('Vrsta prtljage', LUGGAGE_TYPES)
    weight = st.number_input('Največja teža (kg)', min_value=0.1, value=10.0, step=0.5, disabled=not weight_enabled)
    activities = st.multiselect('Načrtovane aktivnosti (neobvezno)', ACTIVITIES)
    submitted = st.form_submit_button('Generiraj seznam za pakiranje')

if submitted:
    st.session_state.pop('snapshot', None)
    try:
        trip = TripInput(destination=destination, departure_date=departure, duration_days=duration,
                         luggage_type=luggage, max_weight_kg=weight if weight_enabled else None,
                         activities=activities)
    except ValidationError as error:
        errors = error.errors(include_input=False, include_context=False)
        if any(item['loc'][:1] == ('destination',) for item in errors):
            st.error('Vnesite destinacijo (mesto in državo).')
        else:
            st.error('Preverite destinacijo, datum, trajanje in pozitivno omejitev teže.')
    else:
        if not gemini_key or not geo_key:
            st.error('Za pripravo seznama nastavite oba ključa API: GEMINI_API_KEY in GEOAPIFY_API_KEY.')
        else:
            try:
                with st.spinner('Pripravljam prilagojen seznam …'):
                    location = geocode_destination(trip.destination, api_key=geo_key)
                    warnings = []
                    try:
                        weather = get_weather_forecast(location, trip.departure_date, trip.duration_days)
                        if weather.status == 'unavailable':
                            warnings.append(weather.message or 'Vremenska napoved za izbrane datume \u0161e ni na voljo.')
                        elif weather.status == 'partial':
                            warnings.append('Vremenska napoved pokriva le del potovanja; za preostale dni ni podatkov.')
                    except ServiceError:
                        weather = None
                        warnings.append('Vremenske napovedi trenutno ni mogoče pridobiti. Seznam bo pripravljen brez napovedi.')
                    try:
                        context = load_packing_data()
                    except ServiceError:
                        context = None
                        warnings.append('Podatki Wikivoyage manjkajo ali so poškodovani. Seznam bo pripravljen brez tega vira.')
                    recommendation = generate_packing_recommendation(trip, location, weather, context, api_key=gemini_key, model=model)
                    generation = st.session_state.get('generation', 0) + 1
                    st.session_state.generation = generation
                    st.session_state.snapshot = dict(trip=trip, location=location, weather=weather,
                        context=context, warnings=warnings, recommendation=recommendation, generation=generation)
            except ServiceError as error:
                st.error(str(error))
            except (ValueError, KeyError, OSError):
                st.error('Podatkov ni bilo mogoče obdelati. Preverite nastavitve in poskusite znova.')

snapshot = st.session_state.get('snapshot')
if snapshot:
    trip, location = snapshot['trip'], snapshot['location']
    st.subheader(f"Seznam za: {location.formatted}")
    st.caption(f'{trip.departure_date:%d. %m. %Y} · {trip.duration_days} dni · {trip.luggage_type}')
    st.caption('Aktivnosti: ' + (', '.join(trip.activities) if trip.activities else 'Splošno potovanje'))
    if trip.max_weight_kg is not None:
        st.caption(f'Omejitev teže: {trip.max_weight_kg:g} kg')
    for warning in snapshot['warnings']:
        st.warning(warning)
    weather = snapshot['weather']
    if weather and weather.days:
        st.write(f'Napoved: {weather.coverage_start:%d. %m. %Y}–{weather.coverage_end:%d. %m. %Y}')
        labels = {0: 'Jasno', 1: 'Pretežno jasno', 2: 'Delno oblačno', 3: 'Oblačno', 45: 'Megla', 48: 'Megla z ivjem'}
        def weather_label(code):
            return labels.get(code, 'Rosenje' if 51 <= code <= 57 else 'Dež' if 61 <= code <= 67 else 'Sneg' if 71 <= code <= 77 else 'Plohe' if 80 <= code <= 86 else 'Nevihta' if 95 <= code <= 99 else 'Neznano')
        units = weather.units
        with st.expander('Dnevna vremenska napoved'):
            st.table([{'Datum': day.date.isoformat(),
                f"Min ({units.get('temperature_2m_min', '°C')})": day.temperature_2m_min,
                f"Max ({units.get('temperature_2m_max', '°C')})": day.temperature_2m_max,
                f"Padavine ({units.get('precipitation_sum', 'mm')})": day.precipitation_sum,
                'Verjetnost padavin (%)': day.precipitation_probability_max,
                'Vreme (WMO)': f'{weather_label(day.weather_code)} ({day.weather_code})',
                f"Veter ({units.get('wind_speed_10m_max', 'km/h')})": day.wind_speed_10m_max} for day in weather.days])
    recommendation = snapshot['recommendation']
    total = sum(len(category.items) for category in recommendation.categories)
    packed = sum(
        bool(st.session_state.get(f"packed_{snapshot['generation']}_{ci}_{ii}", False))
        for ci, category in enumerate(recommendation.categories)
        for ii, item in enumerate(category.items)
    )
    st.write(f'Spakirano: {packed} / {total}')
    st.progress(packed / total)
    for ci, category in enumerate(recommendation.categories):
        with st.expander(f'{category.name} ({len(category.items)})', expanded=True):
            for ii, item in enumerate(category.items):
                label = ' '.join(f'{item.name} - {item.quantity} {item.unit} – {item.reason}'.split())
                st.checkbox(label, key=f"packed_{snapshot['generation']}_{ci}_{ii}")
    if recommendation.general_advice:
        with st.expander('Dodatni nasveti'):
            for advice in recommendation.general_advice:
                st.write(advice)
    st.download_button('Prenesi seznam (JSON)', recommendation.model_dump_json(indent=2), file_name='smartpack.json', mime='application/json')
    context = snapshot['context']
    if context:
        st.caption('Wikivoyage: ' + context['attribution'] + ' · ' + context['license'])
        st.markdown(f"[Članek]({context['source_url']}) · [Zgodovina]({context['source_url']}?action=history)")
st.caption('Lokacije: Geoapify · Vremenski podatki: Open-Meteo')
st.markdown('[Geoapify](https://www.geoapify.com/) · [Open-Meteo](https://open-meteo.com/)')

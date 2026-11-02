"""Naloga 3 (TIDS): interaktiven prikaz turistične statistike OPSI/PC-Axis."""

import streamlit as st

from selection import second_municipality_selection

from data_loader import (
    SOURCE_PAGE,
    PX_URL,
    PXFormatError,
    available_months,
    available_years,
    download_data,
    comparison_trend,
    monthly_trend,
    top_ten,
)

st.set_page_config(page_title="SmartPack | Turistična statistika", page_icon="🧳", layout="wide")

MONTH_NAMES = (
    "Januar", "Februar", "Marec", "April", "Maj", "Junij",
    "Julij", "Avgust", "September", "Oktober", "November", "December",
)


@st.cache_data(ttl=3600, show_spinner="Prenašam in obdelujem podatke PC-Axis ...")
def load_statistics():
    # Vir se prenese pri prvem odpiranju in po poteku predpomnilnika.
    return download_data()


st.title("SmartPack – Turistična statistika Slovenije")
st.write("Prihodi turistov po občinah: najbolj obiskane občine in mesečna sezonskost.")

with st.sidebar:
    st.header("Podatki")
    if st.button("Osveži podatke s SURS"):
        load_statistics.clear()
        st.rerun()
    st.caption("Samodejni prenos ob prvem odprtju; predpomnilnik velja 1 uro.")

try:
    data = load_statistics()
except (RuntimeError, PXFormatError, ValueError) as exc:
    st.error(f"Podatkov ni bilo mogoče naložiti: {exc}")
    st.info("Preverite internetno povezavo in dosegljivost datoteke SURS PC-Axis.")
    st.stop()

with st.sidebar:
    st.header("Filtri")
    years = available_years(data)
    if not years:
        st.error("Ni podatkov za tekoče leto ali preteklih šest let.")
        st.stop()
    year = st.selectbox("Leto", years)
    months = available_months(data, year)
    month = st.selectbox(
        "Mesec (lestvica Top 10)",
        months,
        index=len(months) - 1,
        format_func=lambda m: MONTH_NAMES[m - 1],
    )

st.subheader(f"Top 10 občin – {MONTH_NAMES[month - 1]} {year}")
ranking = top_ten(data, year, month)
if ranking.empty:
    st.warning("Za ta mesec ni podatkov o prihodih turistov.")
else:
    show_list = st.toggle("Prikaži seznam namesto grafa", value=False)
    if show_list:
        listed = ranking.rename(columns={
            "obcina": "Občina", "prihodi": "Prihodi turistov",
        }).copy()
        listed.insert(0, "Mesto", range(1, len(listed) + 1))
        st.dataframe(listed, hide_index=True, use_container_width=True)
    else:
        st.bar_chart(
            ranking, x="obcina", y="prihodi", horizontal=True,
            x_label="Prihodi turistov", y_label="Občina", sort=False,
        )

st.subheader(f"Mesečni prihodi turistov po občini – {year}")
# Ponudimo le občine, ki imajo podatke v izbranem letu.
municipalities = sorted(data.loc[data["godina"] == year, "obcina"].unique())
default = ranking.iloc[0]["obcina"] if not ranking.empty else municipalities[0]
municipality = st.selectbox(
    "Izberite občino", municipalities, index=municipalities.index(default),
    key="first_municipality",
)

# Rezerviramo prostor za graf, da je stikalo za primerjavo pod grafom.
chart_slot = st.empty()
compare = st.toggle("Primerjaj z drugo občino", value=False)

if compare and len(municipalities) > 1:
    # Seznam možnosti druge občine je vedno enak: sprememba prve zato
    # ne ponastavi izbire druge občine (Streamlit veže stanje na možnosti).
    second_key = "second_municipality"
    st.session_state[second_key] = second_municipality_selection(
        municipalities,
        municipality,
        st.session_state.get(second_key),
        st.session_state.get("previous_first_municipality"),
        ranking["obcina"].tolist(),
    )
    second_municipality = st.selectbox(
        "Izberite drugo občino", municipalities, key=second_key,
    )
    if second_municipality == municipality:
        # Uporabnik lahko ročno izbere isto občino. Ne izvajamo
        # primerjave dveh enakih občin, ampak zahtevamo drugo izbiro.
        st.warning("Za primerjavo izberite dve različni občini.")
        trend = monthly_trend(data, municipality, year).rename(
            columns={"prihodi": municipality},
        )
        series = [municipality]
    else:
        trend = comparison_trend(data, municipality, second_municipality, year)
        series = [municipality, second_municipality]
else:
    if compare:
        st.info("Za primerjavo potrebujemo podatke za vsaj dve občini.")
    trend = monthly_trend(data, municipality, year).rename(
        columns={"prihodi": municipality},
    )
    series = [municipality]

# Zapomnimo si prejšnjo prvo občino, da se lahko vlogi po potrebi zamenjata.
st.session_state["previous_first_municipality"] = municipality

chart_slot.line_chart(
    trend, x="mesec", y=series,
    x_label="Mesec", y_label="Prihodi turistov",
)
st.caption("Meseci brez objavljenih podatkov niso prikazani kot 0. "
           "Število prihodov meri registrirane prihode v nastanitvene obrate, ne obiska znamenitosti.")

st.markdown(f"**Vir:** [OPSI / SURS – tabela 2164466S]({SOURCE_PAGE}) · "
            f"[Prenos izvirne datoteke .PX]({PX_URL}) · CC BY 4.0")

"""Lokalni testi z majhnim preverljivim primerom vsebine PC-Axis."""

import unittest
from unittest.mock import Mock, patch

from selection import second_municipality_selection

from data_loader import (
    PXFormatError, available_months, available_years, decode_px,
    download_data, comparison_trend, monthly_trend, parse_px, top_ten,
)

# Osni vrstni red namenoma NI zaporedje, v katerem so dimenzije navedene
# v zahtevah. Tako preverjamo uporabo STUB/HEADING in ne trdo kodiranih indeksov.
PX_SAMPLE = '''CHARSET="UTF-8";
MATRIX="2164466S";
TITLE="Prihodi in prenočitve turistov po občinah";
STUB="OBČINE","MESEC";
HEADING="DRŽAVA","MERITVE";
VALUES("OBČINE")="SLOVENIJA","Bled","Ljubljana","Maribor";
VALUES("MESEC")="2025M01","2025M02","2026M01";
VALUES("DRŽAVA")="0 Država - SKUPAJ","1 DOMAČI","2 TUJI";
VALUES("MERITVE")="Prihodi turistov","Prenočitve turistov";
DATA=
'''


def sample_px():
    cells = []
    for municipality in ("SLOVENIJA", "Bled", "Ljubljana", "Maribor"):
        for period in ("2025M01", "2025M02", "2026M01"):
            for country in ("skupaj", "domaci", "tuji"):
                for measure in ("prihodi", "nocitve"):
                    if municipality == "Ljubljana" and period == "2025M01":
                        count = 200
                    elif municipality == "Bled" and period == "2025M01":
                        count = 150
                    elif municipality == "Maribor" and period == "2025M01":
                        count = 10
                    elif municipality == "Maribor" and period == "2025M02":
                        count = None  # Manjkajoči podatki
                    else:
                        count = 50
                    if country != "skupaj":
                        count = 9999  # Bili bi napačni, če bi jih sešteli.
                    if measure == "nocitve":
                        count = 8888
                    cells.append('".."' if count is None else str(count))
    return (PX_SAMPLE + " ".join(cells) + ";\n").encode("utf-8")


class TestSmartPackOpenData(unittest.TestCase):
    def setUp(self):
        self.raw = sample_px()
        self.data = parse_px(self.raw)

    def test_read_pacxis_dimensions(self):
        self.assertEqual(list(self.data.columns), ["godina", "mesec", "obcina", "prihodi"])
        self.assertEqual(set(self.data["obcina"]), {"Bled", "Ljubljana", "Maribor"})

    def test_country_total_only_and_not_nights(self):
        jan = top_ten(self.data, 2025, 1)
        self.assertEqual(jan.iloc[0]["obcina"], "Ljubljana")
        self.assertEqual(int(jan.iloc[0]["prihodi"]), 200)

    def test_missing_cells_are_not_zeros(self):
        feb = self.data[(self.data["godina"] == 2025) & (self.data["mesec"] == 2)]
        self.assertNotIn("Maribor", set(feb["obcina"]))
        trend = monthly_trend(self.data, "Maribor", 2025)
        self.assertTrue(trend.loc[trend["mesec"] == 2, "prihodi"].isna().all())

    def test_monthly_trend_has_twelve_months(self):
        trend = monthly_trend(self.data, "Bled", 2025)
        self.assertEqual(len(trend), 12)
        self.assertEqual(int(trend.iloc[0]["prihodi"]), 150)
        self.assertTrue(trend.iloc[2:]["prihodi"].isna().all())

    def test_comparison_trend_has_two_distinct_series(self):
        result = comparison_trend(self.data, "Ljubljana", "Bled", 2025)
        self.assertEqual(list(result.columns), ["mesec", "Ljubljana", "Bled"])
        self.assertEqual(len(result), 12)
        self.assertEqual(int(result.iloc[0]["Ljubljana"]), 200)
        self.assertEqual(int(result.iloc[0]["Bled"]), 150)

    def test_comparison_keeps_missing_months_as_nan(self):
        result = comparison_trend(self.data, "Maribor", "Bled", 2025)
        self.assertTrue(result.loc[result["mesec"] == 2, "Maribor"].isna().all())
        self.assertEqual(int(result.loc[result["mesec"] == 2, "Bled"].iloc[0]), 50)
        self.assertTrue(result.loc[result["mesec"] == 12, ["Maribor", "Bled"]].isna().all().all())

    def test_comparison_rejects_same_municipality(self):
        with self.assertRaises(ValueError):
            comparison_trend(self.data, "Bled", "Bled", 2025)

    def test_years_with_six_year_lookback(self):
        self.assertEqual(available_years(self.data, current_year=2026), [2026, 2025])
        self.assertEqual(available_years(self.data, current_year=2032), [2026])
        self.assertEqual(available_years(self.data, current_year=2033), [])

    def test_months_filter(self):
        self.assertEqual(available_months(self.data, 2025), [1, 2])
        self.assertEqual(available_months(self.data, 2026), [1])

    def test_reject_missing_data_block(self):
        with self.assertRaises(PXFormatError):
            parse_px(b'HEADING="MESEC";')

    def test_reject_truncated_data(self):
        with self.assertRaises(PXFormatError):
            parse_px(self.raw[:-10] + b";")

    def test_reject_keys_format(self):
        with self.assertRaises(PXFormatError):
            parse_px(self.raw.replace(b"DATA=", b"KEYS=1;\nDATA="))

    def test_reject_unexpected_axes(self):
        with self.assertRaises(PXFormatError):
            parse_px(self.raw.replace(b"OB\xc4\x8cINE", b"REGIJE"))

    def test_reject_empty_input(self):
        with self.assertRaises(PXFormatError):
            decode_px(b"")

    def test_download_request(self):
        response = Mock(content=self.raw)
        response.raise_for_status.return_value = None
        with patch("data_loader.requests.get", return_value=response) as getter:
            result = download_data()
        self.assertEqual(len(result), len(self.data))
        self.assertTrue(getter.called)
        self.assertTrue(getter.call_args.args[0].endswith(".PX"))


class TestComparisonSelection(unittest.TestCase):
    municipalities = ["Bled", "Ljubljana", "Maribor", "Piran"]
    ranking = ["Ljubljana", "Bled", "Piran", "Maribor"]

    def test_second_stays_selected_when_first_changes(self):
        chosen = second_municipality_selection(
            self.municipalities, "Maribor", "Piran", "Bled", self.ranking,
        )
        self.assertEqual(chosen, "Piran")

    def test_swap_when_first_changes_to_selected_second(self):
        chosen = second_municipality_selection(
            self.municipalities, "Piran", "Piran", "Bled", self.ranking,
        )
        self.assertEqual(chosen, "Bled")

    def test_initial_second_is_next_ranked_distinct_municipality(self):
        chosen = second_municipality_selection(
            self.municipalities, "Ljubljana", None, "Maribor", self.ranking,
        )
        self.assertEqual(chosen, "Bled")

    def test_invalid_second_falls_back_to_available_municipality(self):
        chosen = second_municipality_selection(
            self.municipalities, "Ljubljana", "Koper", None, self.ranking,
        )
        self.assertEqual(chosen, "Bled")


if __name__ == "__main__":
    unittest.main()

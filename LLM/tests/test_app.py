"""Real Streamlit AppTest; external services are mocked, never dependency packages."""
import os
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from streamlit.testing.v1 import AppTest
from LLM.models import Location, PackingRecommendation, ServiceError, WeatherForecast, WeatherDay, LUGGAGE_TYPES, ACTIVITIES

APP = Path(__file__).resolve().parents[1] / 'app.py'


class AppTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key', 'GEOAPIFY_API_KEY': 'test-key'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.location = Location(name='Barcelona', formatted='Barcelona, Spain', country='Spain', latitude=41.4, longitude=2.2)
        self.result = PackingRecommendation(destination='Barcelona', duration_days=7, luggage_type='Nahrbtnik',
            categories=[{'name': 'Oblačila', 'items': [{'name': 'Majica', 'quantity': 7, 'unit': 'kos', 'reason': 'Za vsak dan.'}]}])
        self.mocks = []
        for target, value in [('LLM.geocoding_service.geocode_destination', self.location),
                              ('LLM.weather_service.get_weather_forecast', WeatherForecast(status='unavailable', requested_start=date.today(), requested_end=date.today())),
                              ('LLM.context_service.load_packing_data', {'attribution': 'Wikivoyage contributors', 'license': 'CC BY-SA', 'source_url': 'https://en.wikivoyage.org/wiki/Packing_list'}),
                              ('LLM.llm_service.generate_packing_recommendation', self.result)]:
            patcher = patch(target, return_value=value)
            self.mocks.append(patcher.start())
            self.addCleanup(patcher.stop)
        self.geo, self.weather, self.context, self.llm = self.mocks

    def app(self):
        app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        return app

    def submit(self, app):
        app.text_input[0].set_value('Barcelona')
        app.button[0].click().run()
        self.assertFalse(app.exception)

    def test_initial_view_has_no_api_calls(self):
        self.app()
        for mock in self.mocks:
            mock.assert_not_called()

    def test_missing_configuration_does_not_crash(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': '', 'GEOAPIFY_API_KEY': ''}):
            app = self.app()
            self.submit(app)
        self.assertTrue(app.error)
        self.geo.assert_not_called()

    def test_generation_checkbox_and_second_submission(self):
        app = self.app()
        self.submit(app)
        self.assertIn('Spakirano: 0 / 1', [x.value for x in app.markdown])
        self.assertIn('Vremenska napoved za izbrane datume \u0161e ni na voljo.', [x.value for x in app.warning])
        app.checkbox[1].check().run()
        self.assertTrue(app.checkbox[1].value)
        self.assertEqual(self.llm.call_count, 1)
        self.assertIn('Spakirano: 1 / 1', [x.value for x in app.markdown])
        self.submit(app)
        self.assertEqual(self.llm.call_count, 2)
        self.assertFalse(app.checkbox[1].value)
        self.assertIsNone(self.llm.call_args.args[0].max_weight_kg)

    def test_compact_categories_reasons_and_folded_advice(self):
        self.result.categories[0].items[0].reason = 'Za  vsak\n dan. '
        self.result.categories.append(type(self.result.categories[0])(
            name='Dokumenti', items=[dict(name='Osebna izkaznica', quantity=1,
                                          unit='kos', reason='Za preverjanje identitete.')]))
        self.result.general_advice = ['Preverite dokumente.']
        app = self.app()
        self.submit(app)
        self.assertEqual([x.label for x in app.expander],
                         [f'{self.result.categories[0].name} (1)', 'Dokumenti (1)', 'Dodatni nasveti'])
        self.assertTrue(app.expander[0].proto.expanded)
        self.assertTrue(app.expander[1].proto.expanded)
        self.assertFalse(app.expander[2].proto.expanded)
        self.assertEqual(app.checkbox[1].label, 'Majica - 7 kos – Za vsak dan.')
        self.assertNotIn('Za vsak dan.', [x.value for x in app.caption])
        self.assertEqual(app.get('progress')[0].value, 0)
        app.checkbox[1].check().run()
        self.assertEqual(app.get('progress')[0].value, 50)
        self.assertIn('Spakirano: 1 / 2', [x.value for x in app.markdown])
        self.llm.assert_called_once()
        self.assertEqual(app.session_state['snapshot']['recommendation'].categories[0].items[0].reason,
                         'Za  vsak\n dan. ')

    def test_actual_weather_table_is_folded_with_coverage(self):
        today = date.today()
        self.weather.return_value = WeatherForecast(status='partial', requested_start=today,
            requested_end=today + timedelta(days=6), coverage_start=today, coverage_end=today, days=[WeatherDay(date=today, temperature_2m_min=8,
                temperature_2m_max=18, precipitation_sum=2, weather_code=61,
                wind_speed_10m_max=10)])
        app = self.app()
        self.submit(app)
        self.assertEqual(app.expander[0].label, 'Dnevna vremenska napoved')
        self.assertFalse(app.expander[0].proto.expanded)
        self.assertEqual(len(app.table), 1)
        self.assertEqual(app.table[0].value.iloc[0]['Datum'], today.isoformat())
        coverage = next(x.value for x in app.markdown if x.value.startswith('Napoved:'))
        self.assertEqual(coverage.count(f'{today:%d. %m. %Y}'), 2)
        self.assertTrue(app.warning)

    def test_optional_weight(self):
        app = self.app()
        app.checkbox[0].check().run()
        self.submit(app)
        self.assertEqual(self.llm.call_args.args[0].max_weight_kg, 10)

    def test_unicode_choices_match_model(self):
        app = self.app()
        app.selectbox[0].select(LUGGAGE_TYPES[1])
        app.multiselect[0].select(ACTIVITIES[1])
        self.result.luggage_type = LUGGAGE_TYPES[1]
        self.submit(app)
        self.assertEqual(self.llm.call_args.args[0].luggage_type, LUGGAGE_TYPES[1])
        self.assertEqual(self.llm.call_args.args[0].activities, [ACTIVITIES[1]])

    def test_degraded_sources_continue(self):
        self.weather.side_effect = ServiceError('private details must not display')
        self.context.side_effect = ServiceError('private details must not display')
        app = self.app()
        self.submit(app)
        self.assertEqual(len(app.warning), 2)
        self.assertIsNone(self.llm.call_args.args[2])
        self.assertIsNone(self.llm.call_args.args[3])

    def test_invalid_trip_prevents_calls(self):
        for destination in ('', '   '):
            with self.subTest(destination=destination):
                app = self.app()
                app.text_input[0].set_value(destination)
                app.button[0].click().run()
                self.assertFalse(app.exception)
                self.assertEqual([error.value for error in app.error],
                                 ['Vnesite destinacijo (mesto in državo).'])
                for mock in self.mocks:
                    mock.assert_not_called()

    def test_failed_new_generation_clears_previous_result(self):
        app = self.app()
        self.submit(app)
        self.llm.side_effect = ServiceError('private details must not display')
        self.submit(app)
        self.assertTrue(app.error)
        self.assertFalse(any('Seznam za:' in x.value for x in app.subheader))
        self.assertEqual(len(app.checkbox), 1)

    def test_geocode_failure_prevents_model(self):
        self.geo.side_effect = ServiceError('private details must not display')
        app = self.app()
        self.submit(app)
        self.llm.assert_not_called()
        self.weather.assert_not_called()


if __name__ == '__main__':
    unittest.main()

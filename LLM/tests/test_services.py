import json
import tempfile
import unittest
import sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from unittest.mock import Mock, patch
import requests
from LLM.models import Location, ServiceError
from LLM.geocoding_service import geocode_destination
from LLM.weather_service import get_weather_forecast
from LLM.context_service import load_packing_data


class ServiceTests(unittest.TestCase):
    def response(self, data):
        response = Mock()
        response.json.return_value = data
        return response

    @patch('LLM.geocoding_service.requests.get')
    def test_geocode_success(self, get):
        get.return_value = self.response({'results':[{'name':'Ljubljana','formatted':'Ljubljana, Slovenia','country':'Slovenia','lat':46.05,'lon':14.5}]})
        location = geocode_destination('Ljubljana', 'secret')
        self.assertEqual(location.country, 'Slovenia')
        self.assertEqual((location.latitude,location.longitude,location.formatted),(46.05,14.5,'Ljubljana, Slovenia'))
        self.assertEqual(get.call_args.kwargs['params']['limit'], 1)
        self.assertGreater(get.call_args.kwargs['timeout'], 0)

    @patch('LLM.geocoding_service.requests.get')
    def test_geocode_failures_are_sanitized(self, get):
        for data in [{'results':[]}, {}, {'results':[{'lat':91,'lon':1}]}, {'results':[{'lat':float('nan'),'lon':1}]}, {'results':[{'lat':1,'lon':2}]}, {'results':None}]:
            get.return_value = self.response(data)
            with self.subTest(data=data), self.assertRaises(ServiceError):
                geocode_destination('X','secret')
        for error in [requests.Timeout('secret https://bad'), requests.HTTPError('secret https://bad')]:
            get.side_effect = error
            with self.assertRaises(ServiceError) as caught:
                geocode_destination('X','secret')
            self.assertNotIn('secret',str(caught.exception))
            self.assertNotIn('https',str(caught.exception))
        get.reset_mock()
        with self.assertRaises(ServiceError):
            geocode_destination('X','')
        get.assert_not_called()

    @patch('LLM.geocoding_service.requests.get')
    def test_geocode_bad_status_and_json(self, get):
        for operation in ('raise_for_status', 'json'):
            response=self.response({})
            getattr(response,operation).side_effect=requests.HTTPError('https://secret') if operation=='raise_for_status' else ValueError('bad json')
            get.return_value=response
            with self.assertRaises(ServiceError) as caught:
                geocode_destination('X','secret')
            self.assertNotIn('secret',str(caught.exception))

    def weather(self, start, count=3):
        return {'daily':dict(time=[str(start+timedelta(days=i)) for i in range(count)], temperature_2m_min=[10]*count,temperature_2m_max=[20]*count,precipitation_sum=[0]*count,precipitation_probability_max=[10]*count,weather_code=[1]*count,wind_speed_10m_max=[12]*count), 'daily_units':{'temperature_2m_min':'°C','precipitation_sum':'mm'}}

    @patch('LLM.weather_service.requests.get')
    def test_weather_coverage(self, get):
        start = date.today()
        get.return_value = self.response(self.weather(start))
        loc = Location(name='X',formatted='X',country='Y',latitude=46,longitude=14)
        result = get_weather_forecast(loc,start,3)
        self.assertEqual(result.status,'complete')
        self.assertEqual(result.coverage_end,start+timedelta(days=2))
        self.assertEqual(result.units['precipitation_sum'],'mm')
        self.assertEqual(get.call_args.kwargs['params']['forecast_days'],16)
        self.assertEqual(get_weather_forecast(loc,start,5).status,'partial')
        get.reset_mock()
        self.assertEqual(get_weather_forecast(loc,start+timedelta(days=40),3).status,'unavailable')
        get.assert_not_called()

    @patch('LLM.weather_service.requests.get')
    def test_weather_invalid_observations_and_errors(self, get):
        start = date.today()
        loc = Location(name='X',formatted='X',country='Y',latitude=46,longitude=14)
        for data in [{}, {'daily':None}, []]:
            get.return_value=self.response(data)
            with self.assertRaises(ServiceError):
                get_weather_forecast(loc,start,3)
        cases = [{'daily':{'time':['bad']}}, self.weather(start)]
        cases[-1]['daily']['temperature_2m_min']=[None, 'bad', float('nan')]
        for data in cases:
            get.return_value=self.response(data)
            self.assertEqual(get_weather_forecast(loc,start,3).status,'unavailable')
        data=self.weather(start)
        data['daily']['wind_speed_10m_max']=[None,12,12]
        get.return_value=self.response(data)
        self.assertEqual(get_weather_forecast(loc,start,3).status,'partial')
        data=self.weather(start)
        data['daily']['precipitation_probability_max']=[None,None,None]
        get.return_value=self.response(data)
        self.assertEqual(get_weather_forecast(loc,start,3).status,'complete')
        for error in [requests.Timeout('secret'),requests.HTTPError('https://bad')]:
            get.side_effect=error
            with self.assertRaises(ServiceError) as caught:
                get_weather_forecast(loc,start,3)
            self.assertNotIn('https',str(caught.exception))

    @patch('LLM.weather_service.requests.get')
    def test_weather_bad_status_and_json(self, get):
        loc = Location(name='X',formatted='X',country='Y',latitude=46,longitude=14)
        for operation in ('raise_for_status', 'json'):
            response=self.response({})
            getattr(response,operation).side_effect=requests.HTTPError('https://secret') if operation=='raise_for_status' else ValueError('bad json')
            get.return_value=response
            with self.assertRaises(ServiceError):
                get_weather_forecast(loc,date.today(),1)

    @patch('LLM.weather_service.requests.get')
    def test_short_optional_probability_preserves_core_days(self, get):
        start = date.today()
        loc = Location(name='X',formatted='X',country='Y',latitude=46,longitude=14)
        for probabilities in ([], [10]):
            with self.subTest(probabilities=probabilities):
                data = self.weather(start)
                data['daily']['precipitation_probability_max'] = probabilities
                get.return_value = self.response(data)
                forecast = get_weather_forecast(loc,start,3)
                self.assertEqual(forecast.status,'complete')
                self.assertEqual(len(forecast.days),3)
                self.assertEqual([day.precipitation_probability_max for day in forecast.days], probabilities + [None]*(3-len(probabilities)))

    def test_loader(self):
        actual=load_packing_data()
        self.assertEqual(actual['source'],'Wikivoyage')
        self.assertTrue(actual['categories'][0]['items'])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'packing.json'
            with self.assertRaises(ServiceError): load_packing_data(path)
            path.write_text('{',encoding='utf-8')
            with self.assertRaises(ServiceError): load_packing_data(path)
            path.write_text(json.dumps(actual),encoding='utf-8')
            self.assertEqual(load_packing_data(path),actual)
            path.write_text(json.dumps({'categories':[{'name':'X','items':[2]}]}),encoding='utf-8')
            with self.assertRaises(ServiceError): load_packing_data(path)

"""Geoapify forward geocoding, with credential-safe errors."""
import os
import requests
from pydantic import ValidationError
from .models import Location, ServiceError


def geocode_destination(destination: str, api_key: str | None = None) -> Location:
    key = api_key if api_key is not None else os.environ.get('GEOAPIFY_API_KEY', '')
    if not key or not key.strip():
        raise ServiceError('Manjka ključ GEOAPIFY_API_KEY za iskanje destinacije.')
    try:
        response = requests.get('https://api.geoapify.com/v1/geocode/search', params={'text': destination, 'format': 'json', 'limit': 1, 'apiKey': key}, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise ServiceError('Iskanje destinacije trenutno ni uspelo. Poskusite znova.') from None
    try:
        results = payload.get('results')
        if not results:
            raise ServiceError('Destinacije ni bilo mogoče najti. Vnesite natančnejši kraj.')
        data = results[0]
        return Location(name=data.get('name') or data.get('city') or data.get('formatted'), formatted=data['formatted'], country=data['country'], latitude=data['lat'], longitude=data['lon'])
    except (AttributeError, TypeError, KeyError, IndexError, ValidationError):
        raise ServiceError('Storitev je vrnila neveljavne podatke o destinaciji.') from None

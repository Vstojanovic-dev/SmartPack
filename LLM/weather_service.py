"""Open-Meteo daily forecasts, restricted to actually observed trip dates."""
from datetime import date, timedelta
import math
import requests
from .models import Location, WeatherDay, WeatherForecast, ServiceError

FIELDS = ('temperature_2m_min', 'temperature_2m_max', 'precipitation_sum', 'precipitation_probability_max', 'weather_code', 'wind_speed_10m_max')


def get_weather_forecast(location: Location, departure_date: date, duration_days: int) -> WeatherForecast:
    if isinstance(duration_days, bool) or not isinstance(duration_days, int) or not 1 <= duration_days <= 60:
        raise ValueError('Trajanje mora biti med 1 in 60 dni.')
    end = departure_date + timedelta(days=duration_days-1)
    result = WeatherForecast(status='unavailable', requested_start=departure_date, requested_end=end, message='Vremenska napoved za izbrane datume še ni na voljo.')
    # A two-day margin tolerates UTC/local-date differences without guessing a cutoff.
    if departure_date > date.today() + timedelta(days=17):
        return result
    try:
        response = requests.get('https://api.open-meteo.com/v1/forecast', params={'latitude':location.latitude, 'longitude':location.longitude, 'timezone':'auto', 'forecast_days':16, 'daily':','.join(FIELDS)}, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise ServiceError('Vremenske napovedi trenutno ni mogoče pridobiti.') from None
    if not isinstance(payload, dict):
        raise ServiceError('Storitev je vrnila neveljavne vremenske podatke.')
    units = payload.get('daily_units')
    if isinstance(units, dict):
        result.units = {key:value for key,value in units.items() if isinstance(value,str)}
    daily = payload.get('daily')
    if not isinstance(daily, dict) or not isinstance(daily.get('time'), list):
        raise ServiceError('Storitev je vrnila neveljavne vremenske podatke.')
    seen = set()
    for index, raw_date in enumerate(daily['time']):
        try:
            day = date.fromisoformat(raw_date)
            if not departure_date <= day <= end or day in seen:
                continue
            values = {}
            for field in FIELDS:
                array = daily.get(field)
                value = array[index] if isinstance(array, list) and index < len(array) else None
                if field == 'precipitation_probability_max' and value is None:
                    values[field] = None
                    continue
                if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
                    raise ValueError('Missing observation')
                if field == 'weather_code' and not float(value).is_integer():
                    raise ValueError('Invalid weather code')
                values[field] = value
            probability = values['precipitation_probability_max']
            if values['temperature_2m_min'] > values['temperature_2m_max'] or values['precipitation_sum'] < 0 or (probability is not None and not 0 <= probability <= 100) or values['wind_speed_10m_max'] < 0:
                continue
            result.days.append(WeatherDay(date=day, **values))
            seen.add(day)
        except (ValueError, TypeError, IndexError):
            continue
    result.days.sort(key=lambda day:day.date)
    if result.days:
        result.coverage_start = result.days[0].date
        result.coverage_end = result.days[-1].date
        result.status = 'complete' if len(result.days) == duration_days else 'partial'
        result.message = 'Napoved pokriva vse dni potovanja.' if result.status == 'complete' else 'Napoved pokriva samo del potovanja; za preostale dni podatkov ni.'
    return result

import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from datetime import date, timedelta
from pydantic import ValidationError
from LLM.models import TripInput, PackingItem, PackingCategory, PackingRecommendation, LUGGAGE_TYPES, ACTIVITIES


class ModelTests(unittest.TestCase):
    def trip(self, **changes):
        data = dict(destination=' Ljubljana ', departure_date=date.today(), duration_days=3, luggage_type=LUGGAGE_TYPES[0], activities=[ACTIVITIES[0]])
        data.update(changes)
        return TripInput(**data)

    def test_valid_input(self):
        self.assertEqual(self.trip(max_weight_kg=4.5).destination, 'Ljubljana')
        for luggage in LUGGAGE_TYPES:
            self.trip(luggage_type=luggage, activities=list(ACTIVITIES))

    def test_invalid_input_fields(self):
        cases = [('destination', ' '), ('destination', 12), ('departure_date', date.today()-timedelta(days=1)), ('departure_date', 'bad'), ('duration_days', 0), ('duration_days', 61), ('duration_days', True), ('duration_days', '3'), ('duration_days', 3.0), ('luggage_type', 'bad'), ('activities', ['bad']), ('activities', 'Plavanje'), ('max_weight_kg', 0), ('max_weight_kg', -1), ('max_weight_kg', float('inf')), ('max_weight_kg', float('nan')), ('max_weight_kg', True)]
        for field, value in cases:
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                self.trip(**{field: value})

    def test_item_validation(self):
        self.assertEqual(PackingItem(name=' Majica ', quantity=2, reason=' vroče ', unit='kos').name, 'Majica')
        for quantity in [0, -1, True, '2', 2.0]:
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                PackingItem(name='Majica', quantity=quantity, reason='Vroče', unit='kos')
        for field in ['name', 'reason', 'unit']:
            with self.assertRaises(ValidationError):
                PackingItem(**(dict(name='Majica', quantity=1, reason='Vroče', unit='kos') | {field:' '}))

    def test_category_and_recommendation(self):
        item = dict(name='Majica', quantity=1, reason='Vroče', unit='kos')
        cat = dict(name='Oblačila', items=[item])
        data = dict(destination='Ljubljana', duration_days=2, luggage_type=LUGGAGE_TYPES[0], categories=[cat], general_advice=[])
        self.assertEqual(PackingRecommendation(**data).duration_days, 2)
        for field, value in [('destination',' '), ('duration_days',True), ('duration_days',61), ('luggage_type','bad'), ('categories',[])]:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                PackingRecommendation(**(data | {field:value}))
        for category in [dict(name=' ',items=[item]), dict(name='X',items=[]), dict(name='X',items=[item,item | {'name':'  MAJICA  '}])]:
            with self.assertRaises(ValidationError):
                PackingCategory(**category)
        with self.assertRaises(ValidationError):
            PackingRecommendation(**(data | {'categories':[cat, dict(name='Drugo',items=[item])]}))


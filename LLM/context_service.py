"""Load the existing parser artifact without invoking the parser."""
import json
from pathlib import Path
from .models import ServiceError

PACKING_DATA_PATH = Path(__file__).resolve().parent.parent / 'Parser' / 'data' / 'packing_data.json'


def load_packing_data(path: Path | str | None = None) -> dict:
    try:
        data = json.loads(Path(path if path is not None else PACKING_DATA_PATH).read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('categories'), list) or not data['categories']:
            raise ValueError('Invalid categories')
        for category in data['categories']:
            if not isinstance(category, dict) or not isinstance(category.get('name'), str) or not category['name'].strip() or not isinstance(category.get('items'), list) or not category['items'] or any(not isinstance(item,str) or not item.strip() for item in category['items']):
                raise ValueError('Invalid category')
        for field in ('attribution','license','source_url'):
            if not isinstance(data.get(field), str) or not data[field].strip():
                raise ValueError('Missing attribution metadata')
        return data
    except (OSError, UnicodeError, ValueError):
        raise ServiceError('Podatkov Wikivoyage ni mogoče prebrati. Preverite Parser/data/packing_data.json.') from None

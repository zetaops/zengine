from collections import defaultdict
from datetime import datetime, date
from pyoko.field import DATE_FORMAT, DATE_TIME_FORMAT

from pyoko.form import Form
from zengine.lib.cache import Cache


class CatalogData(object):
    def __init__(self, current, key):
        self.lang = current.lang_code
        self.cache_key_tmp = 'CTDT_{key}_{lang_code}'

    def get_from_db(self, key):
        from pyoko.db.connection import client
        data = client.bucket_type('catalog').bucket('ulakbus_settings_fixtures').get(key).data
        self.parse_db_data(data, key)

    def parse_db_data(self, data, key):
        lang_dict = defaultdict(dict)
        for k, v in data.items():
            for lang_code, lang_val in v.items():
                lang_dict[lang_code][k] = lang_val

        for lang_code, lang_set in lang_dict.items():
            Cache(self.cache_key_tmp.format(key=key, lang_code=lang_code)).set(lang_set)

    def get_from_cache(self, key):
        return Cache(self.cache_key_tmp.format(key=key, lang_code=self.lang)).get()

    def get(self, key):
        return self.get_from_cache(key) or self.get_from_db(key)


class JsonForm(Form):
    def serialize(self):
        result = {
            "schema": {
                "title": self.Meta.title,
                "type": "object",
                "properties": {},
                "required": []
            },
            "form": [
                {
                    "type": "help",
                    "helpvalue": getattr(self.Meta, 'help_text', '')
                }
            ],
            "model": {}
        }
        for itm in self._serialize():
            if isinstance(itm['value'], datetime):
                itm['value'] = itm['value'].strftime(DATE_TIME_FORMAT)
            elif isinstance(itm['value'], date):
                itm['value'] = itm['value'].strftime(DATE_FORMAT)

            item_props = {'type': itm['type'], 'title': itm['title']}
            if itm['type'] == 'model':
                item_props['model_name'] = itm['model_name']
            if 'schema' in itm:
                item_props['schema'] = itm['schema']
            result["schema"]["properties"][itm['name']] = item_props

            result["model"][itm['name']] = itm['value'] or itm['default']
            result["form"].append(itm['name'])
            if itm['required']:
                result["schema"]["required"].append(itm['name'])
        return result

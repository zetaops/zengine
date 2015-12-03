from collections import defaultdict
from datetime import datetime, date

import six

from pyoko.fields import DATE_FORMAT, DATE_TIME_FORMAT
from pyoko.form import Form
from zengine.lib.catalog_data import catalog_data_manager

_choices_cache = {}


def convert_choices(chc):
    _id = id(chc)
    _choices_cache[_id] = [{'name': name, 'value': value} for value, name in chc]
    return _choices_cache[_id]


class JsonForm(Form):
    def serialize(self, readable=False):
        result = {
            "schema": {
                "title": self.title,
                "type": "object",
                "properties": {},
                "required": []
            },
            "form": [
                {
                    "type": "help",
                    "helpvalue": self.help_text
                }
            ],
            "model": {}
        }

        if self._model.is_in_db():
            result["model"]['object_key'] = self._model.key
            result["model"]['unicode'] = six.text_type(self._model)

        for itm in self._serialize(readable):
            item_props = {'type': itm['type'], 'title': itm['title']}
            result["model"][itm['name']] = itm['value'] or itm['default']

            if itm['type'] == 'model':
                item_props['model_name'] = itm['model_name']

            if itm['type'] not in ['ListNode', 'model', 'Node']:
                if 'hidden' in itm['kwargs']:
                    # we're simulating HTML's hidden form fields
                    # by just setting it in "model" dict and bypassing other parts
                    continue
                else:
                    item_props.update(itm['kwargs'])

            self._handle_choices(itm, item_props, result)

            if 'schema' in itm:
                item_props['schema'] = itm['schema']

            result["schema"]["properties"][itm['name']] = item_props

            if itm['required']:
                result["schema"]["required"].append(itm['name'])
        return result

    def _handle_choices(self, itm, item_props, result):
        # ui expects a different format for select boxes
        if itm.get('choices'):
            choices = itm.get('choices')
            item_props['type'] = 'select'
            if not isinstance(choices, (list, tuple)):
                choices_data = catalog_data_manager.get_all(itm['choices'])
            else:
                choices_data = _choices_cache.get(id(choices), convert_choices(choices))
            result["form"].append({'key': itm['name'],
                                   'type': 'select',
                                   'title': itm['title'],
                                   'titleMap': choices_data})
        else:
            result["form"].append(itm['name'])

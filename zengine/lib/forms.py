from collections import defaultdict
from datetime import datetime, date
from pyoko.fields import DATE_FORMAT, DATE_TIME_FORMAT
from pyoko.form import Form
from zengine.lib.catalog_data import CatalogData


class JsonForm(Form):
    def serialize(self):
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
        cat_data = CatalogData(self.context)
        for itm in self._serialize():
            if isinstance(itm['value'], datetime):
                itm['value'] = itm['value'].strftime(DATE_TIME_FORMAT)
            elif isinstance(itm['value'], date):
                itm['value'] = itm['value'].strftime(DATE_FORMAT)

            item_props = {'type': itm['type'],
                          'title': itm['title'],
                          }

            if itm.get('cmd'):
                item_props['cmd'] = itm['cmd']

            # ui expects a different format for select boxes
            if itm.get('choices'):
                choices = itm.get('choices')
                if not isinstance(choices, (list, tuple)):
                    choices_data = cat_data.get(itm['choices'])
                else:
                    choices_data = choices
                result["form"].append({'key': itm['name'],
                                       'type': 'select',
                                       'title': itm['title'],
                                       'titleMap': choices_data})
            else:
                result["form"].append(itm['name'])

            if itm['type'] == 'model':
                item_props['model_name'] = itm['model_name']

            if 'schema' in itm:
                item_props['schema'] = itm['schema']

            result["schema"]["properties"][itm['name']] = item_props

            result["model"][itm['name']] = itm['value'] or itm['default']

            if itm['required']:
                result["schema"]["required"].append(itm['name'])
        return result

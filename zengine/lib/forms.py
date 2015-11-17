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

        if self._model.is_in_db():
            # key = self._model.key
            # result["schema"]["properties"]['_id'] = {"type": "string", "title": ""}
            result["model"]['object_key'] = self._model.key
            # result["form"].append("_id")
            # result["schema"]["required"].append('_id')

        for itm in self._serialize():

            item_props = {'type': itm['type'],
                          'title': itm['title'],
                          }
            # if itm['name'] in self.Meta.attributes:
            #     item_props['attributes'] = self.Meta.attributes[itm['name']]

            if itm.get('cmd'):
                item_props['cmd'] = itm['cmd']
            if itm.get('flow'):
                item_props['flow'] = itm['flow']
            if itm.get('position'):
                item_props['position'] = itm['position']

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

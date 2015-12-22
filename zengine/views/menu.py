# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from collections import defaultdict

from pyoko.lib.utils import get_object_from_path
from pyoko.lib.utils import lazy_property
from pyoko.model import model_registry
from zengine.auth.permissions import get_workflows
from zengine.views.base import BaseView
from zengine.config import settings


class Menu(BaseView):
    def __init__(self, current):
        super(Menu, self).__init__(current)
        self.output['quick_menu'] = []
        if settings.ENABLE_SIMPLE_CRUD_MENU:
            result = self.simple_crud()
        else:
            result = self.get_crud_menus()
        for k, v in self.get_workflow_menus().items():
            result[k].extend(v)
        if current.user.superuser:
            result['other'].extend(settings.ADMIN_MENUS)
        self.output.update(result)
        self.add_user_data()
        self.output['settings'] = {
            'static_url': settings.S3_PUBLIC_URL,
        }

    @lazy_property
    def file_manager(self):
        return get_object_from_path(settings.FILE_MANAGER)

    def add_user_data(self):
        usr = self.current.user
        self.output['current_user'] = {
            "name": usr.name,
            "surname": usr.surname,
            "username": usr.username,
            "role": self.current.role.abstract_role.name,
            "avatar": self.file_manager.get_url(usr.avatar),
            "is_staff": self.current.role.typ == 1,
            "is_student": self.current.role.typ == 2,
            "roles": [{"role": role.role.__unicode__()} for role in self.current.user.role_set]
        }

    def reporters(self, results):
        for mdl in ReporterRegistry.get_reporters():
            results['other'].append({"text": mdl.Meta.verbose_name_plural,
                                     "wf": 'crud',
                                     "model": mdl.__name__,
                                     "kategori": settings.DEFAULT_OBJECT_CATEGORY_NAME,
                                     "param": 'id'})
    def simple_crud(self):
        results = defaultdict(list)
        for mdl in model_registry.get_base_models():
            results['other'].append({"text": mdl.Meta.verbose_name_plural,
                                     "wf": 'crud',
                                     "model": mdl.__name__,
                                     "kategori": settings.DEFAULT_OBJECT_CATEGORY_NAME,
                                     "param": 'id'})
        return results

    def get_crud_menus(self):
        results = defaultdict(list)
        for object_type in settings.OBJECT_MENU:
            for model_data in settings.OBJECT_MENU[object_type]:
                if self.current.has_permission(model_data['name']):
                    self.add_crud(model_data, object_type, results)
        return results

    def add_crud(self, model_data, user_type, results):
        model = model_registry.get_model(model_data['name'])
        field_name = model_data.get('field', user_type + '_id')
        verbose_name = model_data.get('verbose_name', model.Meta.verbose_name_plural)
        category = model_data.get('category', settings.DEFAULT_OBJECT_CATEGORY_NAME)
        wf_dict = {"text": verbose_name,
                   "wf": model_data.get('wf', "crud"),
                   "model": model_data['name'],
                   "kategori": category,
                   "param": field_name}
        results[user_type].append(wf_dict)
        self.add_to_quick_menu(wf_dict['model'], wf_dict)

    def add_to_quick_menu(self, key, wf):
        if key in settings.QUICK_MENU:
            self.output['quick_menu'].append(wf)

    def get_workflow_menus(self):
        results = defaultdict(list)
        for wf in get_workflows():
            if self.current.has_permission(wf.spec.name):
                self.add_wf(wf, results)
        return results

    def add_wf(self, wf, results):
        category = wf.spec.wf_properties.get("menu_category", settings.DEFAULT_WF_CATEGORY_NAME)
        object_of_wf = wf.spec.wf_properties.get('object', 'other')
        if category != 'hidden':
            wf_dict = {
                "text": wf.spec.wf_name,
                "wf": wf.spec.name,
                "kategori": category,
                "param": "id"}
            results[object_of_wf].append(wf_dict)
            self.add_to_quick_menu(wf_dict['wf'], wf_dict)

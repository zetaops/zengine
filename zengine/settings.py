# -*-  coding: utf-8 -*-
"""
Zengine Default Project Settings
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


import os.path


#: Default lang
#: Multi-language support not implemented yet.
DEFAULT_LANG = 'en'


#: Project base
BASE_DIR = os.path.dirname(os.path.realpath(__file__))


#: Path of the activity modules which will be invoked by workflow tasks
ACTIVITY_MODULES_IMPORT_PATHS = ['zengine.views']


#: Absolute path to the workflow packages
WORKFLOW_PACKAGES_PATHS = [os.path.join(BASE_DIR, 'diagrams')]


#: Authentication backend
AUTH_BACKEND = 'zengine.auth.auth_backend.AuthBackend'


#: Permissions model
PERMISSION_MODEL = 'zengine.models.Permission'


#: User model
USER_MODEL = 'zengine.models.User'


#: Role model
ROLE_MODEL = 'zengine.models.Role'


#: Logging Settings
#:
#: Left blank to use StreamHandler aka stderr
#:
#: Set to 'file' for logging 'LOG_FILE'
LOG_HANDLER = os.environ.get('LOG_HANDLER')

#: Logging Level. Can be one INFO or DEBUG.
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG')


#: Log file path.
LOG_FILE = os.environ.get('LOG_FILE', '/tmp/zengine.log')


#: Default cache expire time in seconds
DEFAULT_CACHE_EXPIRE_TIME = 99999999


#: Workflows that dosen't require logged in user.
ANONYMOUS_WORKFLOWS = ['login', 'login.']


#: Currently only affects logging level
DEBUG = bool(int(os.environ.get('DEBUG', 0)))


#: Pyoko (DB) Settings
#:
#: Bucket Type
DEFAULT_BUCKET_TYPE = os.environ.get('DEFAULT_BUCKET_TYPE', 'zengine_models')

#: RIAK Server address
RIAK_SERVER = os.environ.get('RIAK_SERVER', 'localhost')


#: Riak access protocol. Can be 'http' or 'pbc'
RIAK_PROTOCOL = os.environ.get('RIAK_PROTOCOL', 'http')


#: Riak port. By default 8098 for http, 8087 for pbc.
RIAK_PORT = os.environ.get('RIAK_PORT', 8098)


#: Redis address and port.
REDIS_SERVER = os.environ.get('REDIS_SERVER', '127.0.0.1:6379')


#: Allowed origins for serving client from a different host.
ALLOWED_ORIGINS = [
                      'http://127.0.0.1:8080',
                      'http://127.0.0.1:9001',
                  ] + os.environ.get('ALLOWED_ORIGINS', '').split(',')


#: Enabled middlewares.
ENABLED_MIDDLEWARES = [
    'zengine.middlewares.CORS',
    'zengine.middlewares.RequireJSON',
    'zengine.middlewares.JSONTranslator',
]


#: Beaker session options.
SESSION_OPTIONS = {
    'session.cookie_expires': True,
    'session.type': 'redis',
    'session.url': REDIS_SERVER,
    'session.auto': True,
    'session.path': '/',
}


#: View URL list for non-workflow views.
#:
#: ('falcon URI template', 'python path to view method/class'),
VIEW_URLS = [
    ('/menu', 'zengine.views.menu.Menu'),
]


#: Relation focused CRUD menus with category support.
#:
#: >>> 'object_type': [{ 'name':'ModelName',
#: >>>                  'field':'field_name',
#: >>>                  'verbose_name': 'verbose_name',
#: >>>                  'category': 'Genel'
#: >>>                  'wf':'crud'}]
#:
#: Entries can be listed under custom categories.
#:
#: object_type is common relation for a group of models.
#:
#: e.g.: ``Teacher`` can be an object_type (grouper) for ``Student``
#: and ``Lecture`` models.
#:
#: 'field' defaults to 'object_type'
#:
#: verbose_name can be specified to override the model's verbose_name_plural
OBJECT_MENU = []

#: List of menu entries for Dashoboard Quick Menu.
QUICK_MENU = []

#: System Messages
MESSAGES = {
    'lane_change_invite_title': 'System needs you!',
    'lane_change_invite_body': 'Some workflow reached a state that needs your action, '
                                'please follow the link bellow',
    'lane_change_message_title': '',
    'lane_change_message_body': 'Some workflow reached a state that needs your action, '
                                'please follow the link bellow',

}


#: A manager object for DB stored catalog data.
CATALOG_DATA_MANAGER = 'zengine.lib.catalog_data.catalog_data_manager'


#: Default category for un-categorized workflows.
DEFAULT_WF_CATEGORY_NAME = 'General Workflows'


#: Enable auto generated CRUD menu for all models.
ENABLE_SIMPLE_CRUD_MENU = True


#: Category name for auto generated CRUD items.
DEFAULT_OBJECT_CATEGORY_NAME = 'Object Tasks'


#: Default date format
DATE_DEFAULT_FORMAT = "%d.%m.%Y"


#: Default datetime format
DATETIME_DEFAULT_FORMAT = "%d.%m.%Y %H:%s"


#: Permission provider.
#: UpdatePermissions command uses this object to get available permmissions
PERMISSION_PROVIDER = 'zengine.auth.permissions.get_all_permissions'


#: Max number of items for non-filtered dropdown boxes.
MAX_NUM_DROPDOWN_LINKED_MODELS = 20


#: Internal Server Error message description
ERROR_MESSAGE_500 = 'Internal Server Error'

# -*-  coding: utf-8 -*-
"""
Zengine Default Project Settings
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from pyoko.settings import *
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

#: AbstractRole model
ABSTRACT_ROLE_MODEL = 'zengine.models.AbstractRole'

#: Role model
ROLE_MODEL = 'zengine.models.Role'

#: Unit model
UNIT_MODEL = 'zengine.models.Unit'

MQ_HOST = os.getenv('MQ_HOST', 'localhost')
MQ_PORT = int(os.getenv('MQ_PORT', '5672'))
MQ_USER = os.getenv('MQ_USER', 'guest')
MQ_PASS = os.getenv('MQ_PASS', 'guest')
MQ_VHOST = os.getenv('MQ_VHOST', '/')

#: Logging Settings
#:
#: Left blank to use StreamHandler aka stderr
#:
#: Set to 'file' for logging 'LOG_FILE'
LOG_HANDLER = os.environ.get('LOG_HANDLER', 'file')

#: Logging Level. Can be one INFO or DEBUG.
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG')

#: Log file path.
LOG_FILE = os.environ.get('LOG_FILE', './zengine.log')

#: Default cache expire time in seconds
DEFAULT_CACHE_EXPIRE_TIME = 99999999

#: Workflows that dosen't require logged in user.
ANONYMOUS_WORKFLOWS = ['login', 'reset_cache',]

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

#: Redis password (password).
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)

#: Riak port. By default 8098 for http, 8087 for pbc.
RIAK_PORT = os.environ.get('RIAK_PORT', 8098)

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
#: ('URI template', 'python path to view method/class'),
VIEW_URLS = {
    'dashboard': 'zengine.views.menu.Menu',
    'sessid_to_userid': 'zengine.views.system.sessid_to_userid',
    'mark_offline_user': 'zengine.views.system.mark_offline_user',
    'ping': 'zengine.views.dev_utils.Ping',
    '_zops_create_message': 'zengine.messaging.views.create_message',
    '_zops_show_channel': 'zengine.messaging.views.show_channel',
    '_zops_list_channels': 'zengine.messaging.views.list_channels',
    '_zops_channel_history': 'zengine.messaging.views.channel_history',
    '_zops_report_last_seen_message': 'zengine.messaging.views.report_last_seen_message',
    '_zops_create_channel': 'zengine.messaging.views.create_channel',
    '_zops_add_members': 'zengine.messaging.views.add_members',
    '_zops_add_unit_to_channel': 'zengine.messaging.views.add_unit_to_channel',
    '_zops_search_user': 'zengine.messaging.views.search_user',
    '_zops_search_unit': 'zengine.messaging.views.search_unit',
    '_zops_create_direct_channel': 'zengine.messaging.views.create_direct_channel',
    '_zops_find_message': 'zengine.messaging.views.find_message',
    '_zops_delete_message': 'zengine.messaging.views.delete_message',
    '_zops_edit_message': 'zengine.messaging.views.edit_message',
    '_zops_get_message_actions': 'zengine.messaging.views.get_message_actions',
    '_zops_add_to_favorites': 'zengine.messaging.views.add_to_favorites',
    '_zops_remove_from_favorites': 'zengine.messaging.views.remove_from_favorites',
    '_zops_list_favorites': 'zengine.messaging.views.list_favorites',
    '_zops_edit_channel': 'zengine.messaging.views.edit_channel',
    '_zops_delete_channel': 'zengine.messaging.views.delete_channel',
    '_zops_pin_channel': 'zengine.messaging.views.pin_channel',
    '_zops_flag_message': 'zengine.messaging.views.flag_message',
    '_zops_unflag_message': 'zengine.messaging.views.unflag_message',
    '_zops_unread_count': 'zengine.messaging.views.unread_count',
    '_zops_unread_notifications': 'zengine.messaging.views.unread_notifications',
    # '_zops_': 'zengine.messaging.views.',
}

if DEBUG:
    VIEW_URLS.update({
        'session_fixture': 'zengine.views.dev_utils.SessionFixture',
        'db_stats': 'zengine.views.dev_utils.DBStats',
        'reset_cache': 'zengine.views.dev_utils.ResetCache'
    })

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
OBJECT_MENU = {}

#: List of menu entries for Dashoboard Quick Menu.
QUICK_MENU = []

#: System Messages
MESSAGES = {
    'lane_change_invite_title': 'System needs you!',
    'lane_change_invite_body': 'Some workflow reached a state that needs your action, '
                               'please follow the link bellow',
    'lane_change_message_title': 'Thank you!',
    'lane_change_message_body': 'You have completed your part on this workflow. '
                                'Interested parties are notified to join and take over the job.',

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
DATETIME_DEFAULT_FORMAT = "%d.%m.%Y %H:%S"

#: Permission provider.
#: UpdatePermissions command uses this object to get available permmissions
PERMISSION_PROVIDER = 'zengine.auth.permissions.get_all_permissions'

#: Max number of items for non-filtered dropdown boxes.
MAX_NUM_DROPDOWN_LINKED_MODELS = 20

#: Internal Server Error message description
ERROR_MESSAGE_500 = 'Internal Server Error'

#: These models will not flushed when running tests
TEST_FLUSHING_EXCLUDES = 'Permission,User,Role'


#: User search method of messaging subsystem will work on these fields
MESSAGING_USER_SEARCH_FIELDS = ['username', 'name', 'surname']

#: Unit search method of messaging subsystem will work on these fields
MESSAGING_UNIT_SEARCH_FIELDS = ['name',]


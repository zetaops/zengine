# -*-  coding: utf-8 -*-
"""project settings"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


from zengine.settings import *

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
print BASE_DIR
# path of the activity modules which will be invoked by workflow tasks
ACTIVITY_MODULES_IMPORT_PATH = 'example.activities'
# absolute path to the workflow packages
# WORKFLOW_PACKAGES_PATH = os.path.join(BASE_DIR, 'workflows')
#
# AUTH_BACKEND = 'zengine.example.models.AuthBackend'
#
# # left blank to use StreamHandler aka stderr
# LOG_HANDLER = os.environ.get('LOG_HANDLER', 'file')
#
# # logging dir for file handler
# LOG_DIR = os.environ.get('LOG_DIR', '/tmp/')
#
# DEFAULT_CACHE_EXPIRE_TIME = 99999999  # seconds
#
# # workflows that dosen't require logged in user
# ANONYMOUS_WORKFLOWS = ['login',]
#
# #PYOKO SETTINGS
# DEFAULT_BUCKET_TYPE = 'zengine_example'
# RIAK_SERVER = os.environ.get('RIAK_SERVER', 'localhost')
# RIAK_PROTOCOL = os.environ.get('RIAK_PROTOCOL', 'http')
# RIAK_PORT = os.environ.get('RIAK_PORT', 8098)
#
# REDIS_SERVER = os.environ.get('REDIS_SERVER')


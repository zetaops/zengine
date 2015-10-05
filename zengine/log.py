# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import logging
from zengine.config import settings
def getlogger():
    # create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # create console handler and set level to debug
    if settings.LOG_HANDLER == 'file':
        ch = logging.FileHandler(filename=settings.LOG_FILE, mode="w")
    else:
        ch = logging.StreamHandler()
    # ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)
    return logger
log = getlogger()

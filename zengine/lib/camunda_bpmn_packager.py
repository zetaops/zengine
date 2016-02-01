# -*-  coding: utf-8 -*-
"""A BPMN XML Parser for Camunda Modeller, based on SpiffWorklow's BPMN parser."""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
__author__ = "Evren Esat Ozkan"

from SpiffWorkflow.bpmn.storage.Packager import Packager, main
from zengine.lib.camunda_parser import CamundaBMPNParser


class CamundaPackager(Packager):
    """
    Custom packager for output of Camunda Modeller
    """
    def __init__(self, package_file, entry_point_process, meta_data=None, editor=None):
        super(CamundaPackager, self).__init__(package_file, entry_point_process, meta_data, editor)
        self.PARSER_CLASS = CamundaBMPNParser


if __name__ == '__main__':
    main(CamundaPackager)

# -*-  coding: utf-8 -*-
"""
This BPMN parser module takes the following extension elements from Camunda's output xml
 and makes them available in the spec definition of the task.
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from SpiffWorkflow.bpmn.parser.util import full_attr

__author__ = "Evren Esat Ozkan"


import logging
from SpiffWorkflow.bpmn.parser.BpmnParser import BpmnParser
from SpiffWorkflow.bpmn.parser.ProcessParser import ProcessParser
from zengine.lib.utils import DotDict

LOG = logging.getLogger(__name__)


class CamundaBMPNParser(BpmnParser):
    def __init__(self):
        super(CamundaBMPNParser, self).__init__()
        self.PROCESS_PARSER_CLASS = CamundaProcessParser


# noinspection PyBroadException
class CamundaProcessParser(ProcessParser):
    def parse_node(self, node):
        """
        overrides ProcessParser.parse_node
        parses and attaches the inputOutput tags that created by Camunda Modeller
        :param node: xml task node
        :return: TaskSpec
        """
        spec = super(CamundaProcessParser, self).parse_node(node)
        spec.data = self.parse_input_data(node)
        spec.defines = spec.data
        service_class = node.get(full_attr('assignee'))
        if service_class:
            self.parsed_nodes[node.get('id')].service_class = node.get(full_attr('assignee'))
        return spec

    def parse_input_data(self, node):
        data = DotDict()
        try:
            for nod in self._get_input_nodes(node):
                data.update(self._parse_input_node(nod))
        except Exception as e:
            LOG.exception("Error while processing node: %s" % node)
        return data

    @staticmethod
    def _get_input_nodes(node):
        for child in node.getchildren():
            if child.tag.endswith("extensionElements"):
                for gchild in child.getchildren():
                    if gchild.tag.endswith("inputOutput"):
                        children = gchild.getchildren()
                        return children
        return []

    @classmethod
    def _parse_input_node(cls, node):
        """
        :param node: xml node
        :return: dict
        """
        data = {}
        child = node.getchildren()
        if not child and node.get('name'):
            val = node.text
        elif child:  # if tag = "{http://activiti.org/bpmn}script" then data_typ = 'script'
            data_typ = child[0].tag.split('}')[1]
            val = getattr(cls, '_parse_%s' % data_typ)(child[0])
        data[node.get('name')] = val
        return data

    @classmethod
    def _parse_map(cls, elm):
        return dict([(item.get('key'), item.text) for item in elm.getchildren()])

    @classmethod
    def _parse_list(cls, elm):
        return [item.text for item in elm.getchildren()]

    @classmethod
    def _parse_script(cls, elm):
        return elm.get('scriptFormat'), elm.text



# -*-  coding: utf-8 -*-
"""
This BPMN parser module takes the following extension elements from Camunda's output xml
 and makes them available in the spec definition of the task.
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from SpiffWorkflow.bpmn.parser.util import full_attr, BPMN_MODEL_NS, ATTRIBUTE_NS
from SpiffWorkflow.bpmn.storage.BpmnSerializer import BpmnSerializer
from SpiffWorkflow.bpmn.storage.Packager import Packager
from SpiffWorkflow.storage.Serializer import Serializer
from six import StringIO
import xml.etree.ElementTree as ET
__author__ = "Evren Esat Ozkan"

from SpiffWorkflow.bpmn.parser.BpmnParser import BpmnParser
from SpiffWorkflow.bpmn.parser.ProcessParser import ProcessParser
from zengine.lib.utils import DotDict
from zengine.log import log




class CamundaBMPNParser(BpmnParser):
    """
    Parser object to override PROCESS_PARSER_CLASS
    """
    def __init__(self):
        super(CamundaBMPNParser, self).__init__()
        self.PROCESS_PARSER_CLASS = CamundaProcessParser


# noinspection PyBroadException
class CamundaProcessParser(ProcessParser):
    """
    Custom process parser with various extra features.
    """
    def __init__(self, *args, **kwargs):
        super(CamundaProcessParser, self).__init__(*args, **kwargs)
        self.spec.wf_name = self.get_name()
        self.spec.wf_description = self._get_description()
        self.spec.wf_properties = self._get_wf_properties()

    def parse_node(self, node):
        """
        Overrides ProcessParser.parse_node
        Parses and attaches the inputOutput tags that created by Camunda Modeller

        Args:
            node: xml task node
        Returns:
             TaskSpec
        """
        spec = super(CamundaProcessParser, self).parse_node(node)
        spec.data = self._parse_input_data(node)
        spec.data['lane_data'] = self._get_lane_properties(node)
        spec.defines = spec.data
        service_class = node.get(full_attr('assignee'))
        if service_class:
            self.parsed_nodes[node.get('id')].service_class = node.get(full_attr('assignee'))
        return spec

    def _get_description(self):
        """
        Tries to get WF description from 'collabration' or 'process' or 'pariticipant'
        Returns:

        """
        ns = {'ns': '{%s}' % BPMN_MODEL_NS}
        desc = (
            self.doc_xpath('.//{ns}collaboration/{ns}documentation'.format(**ns)) or
            self.doc_xpath('.//{ns}process/{ns}documentation'.format(**ns)) or
            self.doc_xpath('.//{ns}collaboration/{ns}participant/{ns}documentation'.format(**ns))
        )
        if desc:
            return desc[0].findtext('.')

    def _get_wf_properties(self):
        ns = {'ns': '{%s}' % BPMN_MODEL_NS,
              'as': '{%s}' % ATTRIBUTE_NS}
        wf_data = {}
        for path in ('.//{ns}collaboration/*/*/{as}property',
                     './/{ns}process/*/*/{as}property'):
            for a in self.doc_xpath(path.format(**ns)):
                wf_data[a.attrib['name']] = a.attrib['value'].strip()
        return wf_data

    def get_name(self):
        """
        Tries to get WF name from 'process' or 'collobration' or 'pariticipant'

        Returns:
            str. WF name.
        """
        ns = {'ns': '{%s}' % BPMN_MODEL_NS}
        for path in ('.//{ns}process',
                     './/{ns}collaboration',
                     './/{ns}collaboration/{ns}participant/'):
            tag = self.doc_xpath(path.format(**ns))
            if tag:
                name = tag[0].get('name')
                if name:
                    return name
        return self.get_id()

    def _parse_input_data(self, node):
        """
        Parses inputOutput part camunda modeller extensions.
        Args:
            node: SpiffWorkflow Node object.

        Returns:
            Data dict.
        """
        data = DotDict()
        try:
            for nod in self._get_input_nodes(node):
                data.update(self._parse_input_node(nod))
        except Exception as e:
            log.exception("Error while processing node: %s" % node)
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

    def _get_lane_properties(self, node):
        """
        Parses the given XML node

        Args:
            node (xml): XML node.

        .. code-block:: xml

             <bpmn2:lane id="Lane_8" name="Lane 8">
                <bpmn2:extensionElements>
                    <camunda:properties>
                        <camunda:property value="foo,bar" name="perms"/>
                    </camunda:properties>
                </bpmn2:extensionElements>
            </bpmn2:lane>

        Returns:
            {'perms': 'foo,bar'}
        """
        lane_name = self.get_lane(node.get('id'))
        lane_data = {'name': lane_name}
        for a in self.xpath(".//bpmn:lane[@name='%s']/*/*/" % lane_name):
            lane_data[a.attrib['name']] = a.attrib['value'].strip()
        return lane_data

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

class ZopsSerializer(Serializer):
    """
    Deserialize direct XML -> Spec
    """

    def deserialize_workflow_spec(self, xml_content, filename):

        parser = CamundaBMPNParser()
        bpmn = ET.parse(StringIO(xml_content))
        parser.add_bpmn_xml(bpmn, svg=None, filename='%s' % filename)
        return parser.get_spec(filename)


class InMemoryPackager(Packager):
    """
    Creates spiff's wf packages on the fly.
    """
    PARSER_CLASS = CamundaBMPNParser

    @classmethod
    def package_in_memory(cls, workflow_name, workflow_files):
        """
        Generates wf packages from workflow diagrams.

        Args:
            workflow_name: Name of wf
            workflow_files:  Diagram  file.

        Returns:
            Workflow package (file like) object
        """
        s = StringIO()
        p = cls(s, workflow_name, meta_data=[])
        p.add_bpmn_files_by_glob(workflow_files)
        p.create_package()
        return s.getvalue()

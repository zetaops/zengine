from SpiffWorkflow.bpmn.storage.Packager import Packager, main
from zaerp.zengine.camunda_parser import CamundaBMPNParser
__author__ = 'Evren Esat Ozkan'


class CamundaPackager(Packager):

    def __init__(self, package_file, entry_point_process, meta_data=None, editor=None):
        super(CamundaPackager, self).__init__(package_file, entry_point_process, meta_data, editor)
        self.PARSER_CLASS = CamundaBMPNParser


if __name__ == '__main__':
    main(CamundaPackager)

from importlib import import_module
import os.path
from SpiffWorkflow.bpmn.BpmnWorkflow import BpmnWorkflow
from SpiffWorkflow.bpmn.storage.BpmnSerializer import BpmnSerializer
from SpiffWorkflow import Task
from SpiffWorkflow.specs import WorkflowSpec
from SpiffWorkflow.storage import DictionarySerializer
from utils import DotDict

__author__ = 'Evren Esat Ozkan'


class ZEngine(object):
    """
    takes wf
    """
    def __init__(self, **kwargs):

        self.conf = DotDict(kwargs)
        self.current = DotDict()
        self.modules = {}
        self.workflow = BpmnWorkflow
        self.workflow_spec = WorkflowSpec
        self.load_or_create_workflow()
        # self.run()

    def load_or_create_workflow(self):
        """
        tries to load the workflow from session
        creates a new one if it can't find
        :return:
        """
        try:
            workflow_path = self.get_worfklow_path()
            serialized_wf = self.request.session.workflows[workflow_path]
            self.workflow = BpmnWorkflow.deserialize(DictionarySerializer(), serialized_wf)
        except Exception as e:
            print e
            wf_pkg_file = open(self.workflow_name)
            self.workflow_spec = BpmnSerializer().deserialize_workflow_spec(wf_pkg_file)
            self.workflow = BpmnWorkflow(self.workflow_spec)

    def get_worfklow_path(self):
        return "%s/workflows/%s.zip" % (os.path.dirname(os.path.realpath(__file__)), self.workflow_name)

    def save_workflow(self):
        if 'workflows' in self.request.session:
            serialized_wf = self.workflow.serialize(serializer=DictionarySerializer())
            self.request.session['workflows'][self.workflow_name] = serialized_wf
            self.request.session.save()  # TODO: check if this is realy neccessary

    def set_current(self, **kwargs):
        self.current.update(kwargs)
        if 'task' in self.current:
            # TODO: look for a better way for getting the task type
            self.current.type = str(self.current.task).split('(')[1].split(')')[0]
            self.current.spec = self.current.task.task_spec
            self.current.name = self.current.task.get_name()

    def complete_current_task(self):
        self.workflow.complete_task_from_id(self.current.task.id)

    def run(self):
        ready_tasks = self.workflow.get_tasks(state=Task.READY)
        if ready_tasks:
            for task in ready_tasks:
                self.set_current(task=task)
                print("TASK >> %s" % self.current.name, self.current.task.data)
                self.process_callbacks()
                self.complete_current_task()
            self.save_workflow()

    def run_module_method(self, module_method):
        mod_parts = module_method.split('.')
        module = "zaerp.lib.zaerp.service_modules.%s" % mod_parts[:-1]
        method = mod_parts[-1]
        if module not in self.modules:
            self.modules[module] = import_module(module)
        getattr(self.modules[module], method)(self.current)

    def process_callbacks(self):
        if 'callbacks' in self.current.spec.data:
            for cb in self.current.spec.data.callbacks:
                self.run_module_method(cb)

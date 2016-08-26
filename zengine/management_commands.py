# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import glob

import six

from pyoko.db.adapter.db_riak import BlockSave, BlockDelete
from pyoko.exceptions import ObjectDoesNotExist
from pyoko.lib.utils import get_object_from_path
from pyoko.manage import *
from zengine.views.crud import SelectBoxCache


class UpdatePermissions(Command):
    """
    Gets permissions from
    :attr:`~zengine.settings.PERMISSION_PROVIDER`
    then creates
    :attr:`~zengine.settings.PERMISSION_MODEL`
    objects if required.

    Args:
        dry: Dry run. Do nothing, just list.
    """
    CMD_NAME = 'update_permissions'
    HELP = 'Syncs permissions with DB'
    PARAMS = [
        {'name': 'dry', 'action': 'store_true', 'help': 'Dry run, just list new found permissions'},
    ]

    def run(self):
        """
        Creates new permissions.
        """
        from pyoko.lib.utils import get_object_from_path
        from zengine.config import settings
        model = get_object_from_path(settings.PERMISSION_MODEL)
        perm_provider = get_object_from_path(settings.PERMISSION_PROVIDER)
        existing_perms = []
        new_perms = []
        for code, name, desc in perm_provider():
            code = six.text_type(code)
            if self.manager.args.dry:
                exists = model.objects.filter(code=code, name=name)
                if exists:
                    perm = exists[0]
                    new = False
                else:
                    new = True
                    perm = model(code=code, name=name)
            else:
                try:
                    perm = model.objects.get(code)
                    existing_perms.append(perm)
                except ObjectDoesNotExist:
                    perm = model(description=desc, code=code, name=name)
                    perm.key = code
                    perm.save()
                    new_perms.append(perm)
                    # perm, new = model.objects.get_or_create({'description': desc}, code=code, name=name)
                    # if new:
                    #     new_perms.append(perm)
                    # else:
                    #     existing_perms.append(perm)

        report = "\n\n%s permission(s) were found in DB. " % len(existing_perms)
        if new_perms:
            report += "\n%s new permission record added. " % len(new_perms)
        else:
            report += 'No new perms added. '

        if new_perms:
            if not self.manager.args.dry:
                SelectBoxCache.flush(model.__name__)
            report += 'Total %s perms exists.' % (len(existing_perms) + len(new_perms))
            report = "\n + " + "\n + ".join([p.name for p in new_perms]) + report
        if self.manager.args.dry:
            print("\n~~~~~~~~~~~~~~ DRY RUN ~~~~~~~~~~~~~~\n")
        print(report + "\n")


class CreateUser(Command):
    """
    Creates a new user.

    Because this doesn't handle permission and role management,
    this is only useful when new user is a superuser.
    """
    CMD_NAME = 'create_user'
    HELP = 'Creates a new user'
    PARAMS = [
        {'name': 'username', 'required': True, 'help': 'Login username'},
        {'name': 'password', 'required': True, 'help': 'Login password'},
        {'name': 'super', 'action': 'store_true', 'help': 'This is a super user'},
    ]

    def run(self):
        """
        Creates user, encrypts password.
        """
        from zengine.models import User
        user = User(username=self.manager.args.username, superuser=self.manager.args.super)
        user.set_password(self.manager.args.password)
        user.save()
        print("New user created with ID: %s" % user.key)


class RunServer(Command):
    """
    Runs development server.

    Args:
        addr: Listen address. Defaults to 127.0.0.1
        port: Listen port. Defaults to 9001
    """
    CMD_NAME = 'runserver'
    HELP = 'Run the development server'
    PARAMS = [
        {'name': 'addr', 'default': '127.0.0.1',
         'help': 'Listening address. Defaults to 127.0.0.1'},
        {'name': 'port', 'default': '9001', 'help': 'Listening port. Defaults to 9001'},
        {'name': 'server_type', 'default': 'tornado', 'help': 'Server type. Default: "tornado"'
                                                              'Possible values: falcon, tornado'},
    ]

    def run(self):
        """
        Starts a development server for the zengine application
        """
        print("Development server started on http://%s:%s. \n\nPress Ctrl+C to stop\n" % (
            self.manager.args.addr,
            self.manager.args.port)
              )
        if self.manager.args.server_type == 'falcon':
            self.run_with_falcon()
        elif self.manager.args.server_type == 'tornado':
            self.run_with_tornado()

    def run_with_tornado(self):
        """
        runs the tornado/websockets based test server
        """
        from zengine.tornado_server.server import runserver
        runserver(self.manager.args.addr, int(self.manager.args.port))

    def run_with_falcon(self):
        """
        runs the falcon/http based test server
        """
        from wsgiref import simple_server
        from zengine.server import app
        httpd = simple_server.make_server(self.manager.args.addr, int(self.manager.args.port), app)
        httpd.serve_forever()


class RunWorker(Command):
    """
    Runs worker daemon.

    Args:
        addr: Listen address. Defaults to 127.0.0.1
        port: Listen port. Defaults to 9001
    """
    CMD_NAME = 'runworker'
    HELP = 'Run the workflow worker'
    PARAMS = [
        {'name': 'workers', 'default': '1', 'help': 'Number of worker process'},
        {'name': 'autoreload', 'action': 'store_true', 'help': 'Autoreload on changes'},
        {'name': 'paths', 'default': '.',
         'help': 'Directory path(s) for watching changes for auto-reloading. (whitespace separated)'},

    ]

    def run(self):
        """
        Starts a development server for the zengine application
        """
        from zengine.wf_daemon import run_workers, Worker

        worker_count = int(self.manager.args.workers or 1)
        if not self.manager.args.daemonize:
            print("Starting worker(s)")

        if worker_count > 1 or self.manager.args.autoreload:
            run_workers(worker_count,
                        self.manager.args.paths.split(' '),
                        self.manager.args.daemonize)
        else:
            worker = Worker()
            worker.run()


class PrepareMQ(Command):
    """
    Creates necessary exchanges, queues and bindings
    """
    CMD_NAME = 'preparemq'
    HELP = 'Creates necessary exchanges, queues and bindings for messaging subsystem'

    def run(self):
        self.create_user_channels()
        self.create_channel_exchanges()

    def create_user_channels(self):
        from zengine.messaging.model import Channel, Subscriber
        user_model = get_object_from_path(settings.USER_MODEL)
        with BlockSave(Channel):
            for usr in user_model.objects.filter():
                # create private exchange of user
                ch, new = Channel.objects.get_or_create(owner=usr, typ=5)
                print("%s exchange: %s" % ('created' if new else 'existing', ch.code_name))
                # create notification subscription to private exchange
                sb, new = Subscriber.objects.get_or_create(channel=ch,
                                                           user=usr,
                                                           read_only=True,
                                                           name='Notifications',
                                                           defaults=dict(can_manage=True,
                                                                         can_leave=False)
                                                           )
                print("%s notify sub: %s" % ('created' if new else 'existing', ch.code_name))

    def create_channel_exchanges(self):
        from zengine.messaging.model import Channel
        for ch in Channel.objects.filter():
            print("(re)creation exchange: %s" % ch.code_name)
            ch.create_exchange()


class LoadDiagrams(Command):
    """
    Loads wf diagrams from disk to DB
    """

    CMD_NAME = 'load_diagrams'
    HELP = 'Loads workflow diagrams from diagrams folder to DB'
    PARAMS = [
        {'name': 'wf_path', 'default': None, 'help': 'Only update given BPMN diagram'},
        {'name': 'clear', 'action': 'store_true', 'help': 'Clear all task related models'},
        {'name': 'force', 'action': 'store_true', 'help': 'Load BPMN file even if there are active WFInstances exists.'},
    ]

    def run(self):
        """
        read workflows, checks if it's updated,
        tries to update if there aren't any running instances of that wf
        """
        from zengine.models.workflow_manager import DiagramXML, BPMNWorkflow, RunningInstancesExist

        if self.manager.args.clear:
            self._clear_models()
            return

        if self.manager.args.wf_path:
            paths = self.get_wf_from_path(self.manager.args.wf_path)
        else:
            paths = self.get_workflows()
        count = 0
        for wf_name, content in paths:
            wf, wf_is_new = BPMNWorkflow.objects.get_or_create(name=wf_name)
            content = self._tmp_fix_diagram(content)
            diagram, diagram_is_updated = DiagramXML.get_or_create_by_content(wf_name, content)
            if wf_is_new or diagram_is_updated:
                count += 1
                print("%s created or updated" % wf_name.upper())
                try:
                    wf.set_xml(diagram, self.manager.args.force)
                except RunningInstancesExist as e:
                    print(e.message)
                    print("Give \"--force\" parameter to enforce")
        print("%s BPMN file loaded" % count)


    def _clear_models(self):
        from zengine.models.workflow_manager import DiagramXML, BPMNWorkflow, WFInstance
        print("Workflow related models will be cleared")
        c = len(DiagramXML.objects.delete())
        print("%s DiagramXML object deleted" % c)
        c = len(BPMNWorkflow.objects.delete())
        print("%s BPMNWorkflow object deleted" % c)
        c = len(WFInstance.objects.delete())
        print("%s WFInstance object deleted" % c)

    def _tmp_fix_diagram(self, content):
        # Temporary solution for easier transition from old to new xml format
        # TODO: Will be removed after all diagrams converted.
        return content.replace(
            'targetNamespace="http://activiti.org/bpmn"',
            'targetNamespace="http://bpmn.io/schema/bpmn"'
        ).replace(
            'xmlns:camunda="http://activiti.org/bpmn"',
            'xmlns:camunda="http://camunda.org/schema/1.0/bpmn"'
        )

    def get_wf_from_path(self, path):
        """
        load xml from given path
        Args:
            path: diagram path

        Returns:

        """
        with open(path) as fp:
            content = fp.read()
        return [(os.path.basename(os.path.splitext(path)[0]), content), ]

    def get_workflows(self):
        """
        Scans and loads all wf found under WORKFLOW_PACKAGES_PATHS

        Yields: XML content of diagram file

        """
        for pth in settings.WORKFLOW_PACKAGES_PATHS:
            for f in glob.glob("%s/*.bpmn" % pth):
                with open(f) as fp:
                    yield os.path.basename(os.path.splitext(f)[0]), fp.read()

# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import glob

import six
import os
import sys
import tempfile
from distutils.errors import DistutilsError

from pyoko.db.adapter.db_riak import BlockSave, BlockDelete
from pyoko.exceptions import ObjectDoesNotExist
from pyoko.lib.utils import get_object_from_path
from pyoko.manage import *
from zengine.views.crud import SelectBoxCache
from babel.messages import frontend as babel_frontend
from babel.messages.extract import DEFAULT_KEYWORDS as BABEL_DEFAULT_KEYWORDS
from zengine.lib.translation import gettext_lazy as __


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
            report = "\n + " + "\n + ".join([p.name or p.code for p in new_perms]) + report
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


class ExtractTranslations(Command):
    """Extract the translations from the source directories and update language-specific .po files."""
    CMD_NAME = 'extract_translations'
    HELP = 'Extract the translations from the source directories and update language-specific .po files.'
    PARAMS = [
        {'name': 'source', 'action': 'append',
         'help': "The source directory corresponding to a domain, in the form of '<domain>:<directory>'."},
        {'name': 'project', 'help': 'The name of the project.'},
        {'name': 'copyright', 'help': 'The holder of the projects copyright.'},
        {'name': 'version', 'help': 'Version of the project.'},
        {'name': 'contact', 'help': 'The contact address for translations.'}
    ]

    def run(self):
        domains = dict(map(self._prepare_domain, self.manager.args.source))
        self._validate_domains(domains)
        self._extract_translations(domains)
        self._init_update_po_files(domains)
        self._cleanup(domains)

    @staticmethod
    def _prepare_domain(mapping):
        """Prepare a helper dictionary for the domain to temporarily hold some information."""
        # Parse the domain-directory mapping
        try:
            domain, dir = mapping.split(':')
        except ValueError:
            print("Please provide the sources in the form of '<domain>:<directory>'")
            sys.exit(1)

        try:
            default_language = settings.TRANSLATION_DOMAINS[domain]
        except KeyError:
            print("Unknown domain {domain}, check the settings file to make sure"
                  " this domain is set in TRANSLATION_DOMAINS".format(domain=domain))
            sys.exit(1)
        # Create a temporary file to hold the `.pot` file for this domain
        handle, path = tempfile.mkstemp(prefix='zengine_i18n_', suffix='.pot')
        return (domain, {
            'default': default_language,
            'pot': path,
            'source': dir,
        })

    @staticmethod
    def _validate_domains(domains):
        """Check that all domains specified in the settings was provided in the options."""
        missing = set(settings.TRANSLATION_DOMAINS.keys()) - set(domains.keys())
        if missing:
            print('The following domains have been set in the configuration, '
                  'but their sources were not provided, use the `--source` '
                  'option to specify their sources: {domains}'.format(domains=', '.join(missing)))
            sys.exit(1)

    def _extract_translations(self, domains):
        """Extract the translations into `.pot` files"""
        for domain, options in domains.items():
            # Create the extractor
            extractor = babel_frontend.extract_messages()
            extractor.initialize_options()
            # The temporary location to write the `.pot` file
            extractor.output_file = options['pot']
            # Add the comments marked with 'tn:' to the translation file for translators to read. Strip the marker.
            extractor.add_comments = ['tn:']
            extractor.strip_comments = True
            # The directory where the sources for this domain are located
            extractor.input_paths = [options['source']]
            # Pass the metadata to the translator
            extractor.msgid_bugs_address = self.manager.args.contact
            extractor.copyright_holder = self.manager.args.copyright
            extractor.version = self.manager.args.version
            extractor.project = self.manager.args.project
            extractor.finalize_options()
            # Add keywords for lazy translation functions, based on their non-lazy variants
            extractor.keywords.update({
                'gettext_lazy': extractor.keywords['gettext'],
                'ngettext_lazy': extractor.keywords['ngettext'],
                '__': extractor.keywords['gettext'],  # double underscore for lazy
            })
            # Do the extraction
            _run_babel_command(extractor)

    def _init_update_po_files(self, domains):
        """Update or initialize the `.po` translation files"""
        for language in settings.TRANSLATIONS:
            for domain, options in domains.items():
                if language == options['default']: continue  # Default language of the domain doesn't need translations
                if os.path.isfile(_po_path(language, domain)):
                    # If the translation already exists, update it, keeping the parts already translated
                    self._update_po_file(language, domain, options['pot'])
                else:
                    # The translation doesn't exist, create a new translation file
                    self._init_po_file(language, domain, options['pot'])

    def _update_po_file(self, language, domain, pot_path):
        print('Updating po file for {language} in domain {domain}'.format(language=language, domain=domain))
        updater = babel_frontend.update_catalog()
        _setup_babel_command(updater, domain, language, pot_path)
        _run_babel_command(updater)

    def _init_po_file(self, language, domain, pot_path):
        print('Creating po file for {language} in domain {domain}'.format(language=language, domain=domain))
        initializer = babel_frontend.init_catalog()
        _setup_babel_command(initializer, domain, language, pot_path)
        _run_babel_command(initializer)

    def _cleanup(self, domains):
        """Remove the temporary '.pot' files that were created for the domains."""
        for option in domains.values():
            try:
                os.remove(option['pot'])
            except (IOError, OSError):
                # It is not a problem if we can't actually remove the temporary file
                pass


class CompileTranslations(Command):
    """Compile the .po translation files into .mo files, which will be loaded by the workers."""
    CMD_NAME = 'compile_translations'
    HELP = 'Compile the .po translation files into .mo files, which will be loaded by the workers.'

    def run(self):
        for language in settings.TRANSLATIONS:
            for domain, default_lang in settings.TRANSLATION_DOMAINS.items():
                if language == default_lang: continue  # Default language of the domain doesn't need translations
                print('Compiling po file for {language} in domain {domain}'.format(language=language, domain=domain))
                compiler = babel_frontend.compile_catalog()
                _setup_babel_command(compiler, domain, language, _po_path(language, domain))
                _run_babel_command(compiler)


def _run_babel_command(babel):
    try:
        babel.run()
    except DistutilsError as err:  # The extractor throws Distutils errors
        print(str(err))
        sys.exit(1)


def _setup_babel_command(babel, domain, language, input_file):
    babel.initialize_options()
    babel.domain = domain
    babel.locale = language
    babel.input_file = input_file
    babel.directory = babel.output_dir = settings.TRANSLATIONS_DIR
    babel.finalize_options()


def _po_path(language, domain):
    return os.path.join(settings.TRANSLATIONS_DIR, language, 'LC_MESSAGES', '{domain}.po'.format(domain=domain))


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
            for usr in user_model.objects.all():
                # create private exchange of user
                # create notification subscription to private exchange

                ch, new_ch, sb, new_sb = usr.prepare_channels()

                print("%s exchange: %s" % ('created' if new_ch else 'existing', ch.code_name))
                print("%s notify sub: %s" % ('created' if new_sb else 'existing', ch.code_name))

    def create_channel_exchanges(self):
        from zengine.messaging.model import Channel
        for ch in Channel.objects.all():
            print("(re)creation exchange: %s" % ch.code_name)
            ch.create_exchange()


class ClearQueues(Command):
    """
    Creates necessary exchanges, queues and bindings
    """
    CMD_NAME = 'clear_queues'
    HELP = 'Clears various system queues'

    def run(self):
        self.clear_input_queue()

    def clear_input_queue(self):
        from zengine.wf_daemon import Worker
        worker = Worker()
        worker.clear_queue()


class ListSysViews(Command):
    """
    Lists non-workflow system and development views
    """
    CMD_NAME = 'list_views'
    HELP = 'Lists non-workflow system and development views'

    def run(self):
        self.list_system_views()

    def list_system_views(self):
        settings.DEBUG = True
        exec ('from %s import *' % settings.MODELS_MODULE)
        from zengine.lib.decorators import VIEW_METHODS, runtime_importer
        import inspect
        runtime_importer()
        by_file = defaultdict(list)
        for k, v in VIEW_METHODS.items():
            by_file[inspect.getfile(v)].append(k)
        for file, views in by_file.items():
            print("|_ %s" % file)
            for view in views:
                print("  |_   %s" % view)


class LoadDiagrams(Command, BaseThreadedCommand):
    """
    Loads wf diagrams from disk to DB
    """

    CMD_NAME = 'load_diagrams'
    HELP = 'Loads workflow diagrams from diagrams folder to DB'
    PARAMS = [
        {'name': 'wf_path', 'default': None,
         'help': 'Only update given BPMN diagram'},
        {'name': 'threads', 'default': 30, 'help': 'Max number of threads. Defaults to 1'},

        {'name': 'clear', 'action': 'store_true',
         'help': 'Clear all TaskManager related models'},

        {'name': 'force', 'action': 'store_true',
         'help': "(Re)Load BPMN file even if it doesn't updated or"
                 " there are active WFInstances exists."},
    ]

    def run(self):
        """
        read workflows, checks if it's updated,
        tries to update if there aren't any running instances of that wf
        """
        from zengine.lib.cache import WFSpecNames

        if self.manager.args.clear:
            self._clear_models()
            return

        if self.manager.args.wf_path:
            paths = self.get_wf_from_path(self.manager.args.wf_path)
        else:
            paths = self.get_workflows()

        self.count = 0

        self.do_with_submit(self.load_diagram, paths, threads=self.manager.args.threads)

        WFSpecNames().refresh()

        print("%s BPMN file loaded" % self.count)

    def load_diagram(self, paths):
        from zengine.models.workflow_manager import DiagramXML, BPMNWorkflow, RunningInstancesExist

        wf_name, content = paths
        key = 'bpmn_workflow_%s' % wf_name
        wf, wf_is_new = BPMNWorkflow.objects.get_or_create(name=wf_name, key=key)
        content = self._tmp_fix_diagram(content)
        diagram, diagram_is_updated = DiagramXML.get_or_create_by_content(wf_name, content)
        if wf_is_new or diagram_is_updated or self.manager.args.force:
            self.count+=1
            print("%s created or updated" % wf_name.upper())
            try:
                wf.set_xml(diagram, self.manager.args.force)
            except RunningInstancesExist as e:
                print(e.message)
                print("Give \"--force\" parameter to enforce")

    def _clear_models(self):
        from zengine.models.workflow_manager import DiagramXML, BPMNWorkflow, WFInstance, \
            TaskInvitation
        print("Workflow related models will be cleared")
        c = len(DiagramXML.objects.delete())
        print("%s DiagramXML object deleted" % c)
        c = len(BPMNWorkflow.objects.delete())
        print("%s BPMNWorkflow object deleted" % c)
        c = len(WFInstance.objects.delete())
        print("%s WFInstance object deleted" % c)
        c = len(TaskInvitation.objects.delete())
        print("%s TaskInvitation object deleted" % c)

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


class CheckList(Command):
    # change font and type in the shell.
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    CMD_NAME = 'check_list'
    HELP = "The system also checks whether the services are up and running," \
           " whether the models are up-to-date, the environment variables are controlled."

    def run(self):
        self.check_encoding_and_env()
        self.check_mq_connection()
        self.check_riak()
        self.check_redis()
        self.check_migration_and_solr()

    def check_migration_and_solr(self):
        """
            The model or models are checked for migrations that need to be done.
            Solr is also checked.
        """
        from pyoko.db.schema_update import SchemaUpdater
        from socket import error as socket_error
        from pyoko.conf import settings
        from importlib import import_module

        import_module(settings.MODELS_MODULE)
        registry = import_module('pyoko.model').model_registry
        models = [model for model in registry.get_base_models()]
        try:
            print(__(u"Checking migration and solr ..."))
            updater = SchemaUpdater(models, 1, False)
            updater.run(check_only=True)

        except socket_error as e:
            print(__(u"{0}Error not connected, open redis and rabbitmq{1}").format(CheckList.FAIL,
                                                                                   CheckList.ENDC))

    @staticmethod
    def check_redis():
        """
            Redis checks the connection
            It displays on the screen whether or not you have a connection.
        """
        from pyoko.db.connection import cache
        from redis.exceptions import ConnectionError

        try:
            cache.ping()
            print(CheckList.OKGREEN + "{0}Redis is working{1}" + CheckList.ENDC)
        except ConnectionError as e:
            print(__(u"{0}Redis is not working{1} ").format(CheckList.FAIL,
                                                            CheckList.ENDC), e.message)

    @staticmethod
    def check_riak():
        """
            Riak checks the connection
            It displays on the screen whether or not you have a connection.
        """
        from pyoko.db.connection import client
        from socket import error as socket_error

        try:
            if client.ping():
                print(__(u"{0}Riak is working{1}").format(CheckList.OKGREEN, CheckList.ENDC))
            else:
                print(__(u"{0}Riak is not working{1}").format(CheckList.FAIL, CheckList.ENDC))
        except socket_error as e:
            print(__(u"{0}Riak is not working{1}").format(CheckList.FAIL,
                                                          CheckList.ENDC), e.message)

    def check_mq_connection(self):
        """
        RabbitMQ checks the connection
        It displays on the screen whether or not you have a connection.
        """
        import pika
        from zengine.client_queue import BLOCKING_MQ_PARAMS
        from pika.exceptions import ProbableAuthenticationError, ConnectionClosed

        try:
            connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
            channel = connection.channel()
            if channel.is_open:
                print(__(u"{0}RabbitMQ is working{1}").format(CheckList.OKGREEN, CheckList.ENDC))
            elif self.channel.is_closed or self.channel.is_closing:
                print(__(u"{0}RabbitMQ is not working!{1}").format(CheckList.FAIL, CheckList.ENDC))
        except ConnectionClosed as e:
            print(__(u"{0}RabbitMQ is not working!{1}").format(CheckList.FAIL, CheckList.ENDC), e)
        except ProbableAuthenticationError as e:
            print(__(u"{0}RabbitMQ username and password wrong{1}").format(CheckList.FAIL,
                                                                           CheckList.ENDC))

    @staticmethod
    def check_encoding_and_env():
        """
        It brings the environment variables to the screen.
        The user checks to see if they are using the correct variables.
        """
        import sys
        import os
        if sys.getfilesystemencoding() in ['utf-8', 'UTF-8']:
            print(__(u"{0}File system encoding correct{1}").format(CheckList.OKGREEN,
                                                                   CheckList.ENDC))
        else:
            print(__(u"{0}File system encoding wrong!!{1}").format(CheckList.FAIL,
                                                                   CheckList.ENDC))
        check_env_list = ['RIAK_PROTOCOL', 'RIAK_SERVER', 'RIAK_PORT', 'REDIS_SERVER',
                          'DEFAULT_BUCKET_TYPE', 'PYOKO_SETTINGS',
                          'MQ_HOST', 'MQ_PORT', 'MQ_USER', 'MQ_VHOST',
                          ]
        env = os.environ
        for k, v in env.items():
            if k in check_env_list:
                print(__(u"{0}{1} : {2}{3}").format(CheckList.BOLD, k, v, CheckList.ENDC))


class ClearCache(Command):
    CMD_NAME = 'clear_cache'
    HELP = 'DELETES the contents of cache with given cache model'
    PARAMS = [{'name': 'prefix', 'required': True,
               'help': 'Comma separated prefix(es) to be cleared. Say "all" to clear ALL data in cache'}]

    def run(self):
        from pyoko.db.connection import cache

        prefix_name = self.manager.args.prefix
        if prefix_name != "":
            if prefix_name != 'all':
                for name in prefix_name.split(','):
                    keys = cache.keys(name + "*")
                    for key in keys:
                        cache.delete(key)
                    print("%d object(s) deleted from cache with PREFIX %s " % (len(keys), name))
            else:
                all_success = cache.flushall()
                if all_success:
                    print("All objects deleted from cache ")
        else:
            print("\"%s\" not a legal argument!" % prefix_name)

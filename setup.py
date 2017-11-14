from distutils.core import setup
from setuptools import find_packages

setup(
    name='zengine',
    version='0.8.2',
    url='https://github.com/zetaops/zengine',
    license='GPL v3',
    packages=find_packages(exclude=['tests', 'tests.*']),
    author='Zetaops AS',
    author_email='info@zetaops.io',
    description='BPMN workflow based web service framework with advanced '
                'permissions and extensible CRUD features',
    install_requires=['beaker', 'passlib', 'falcon', 'beaker_extensions', 'lazy_object_proxy',
                      'redis', 'enum34', 'werkzeug', 'celery', 'SpiffWorkflow', 'pyoko',
                      'tornado', 'pika==0.10.0', 'babel', 'futures',],
    dependency_links=[
        'git+https://github.com/didip/beaker_extensions.git#egg=beaker_extensions',
        'git+https://github.com/zetaops/SpiffWorkflow.git#egg=SpiffWorkflow',
    ],
    package_data={
        'zengine': ['diagrams/*.bpmn'],
    },
    keywords=['web', 'framework', 'rest', 'service',
              'json', 'bpmn', 'workflow', 'web service',
              'orm', 'nosql', 'bpmn 2', 'crud', 'scaffolding'],
)









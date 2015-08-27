from distutils.core import setup
from setuptools import find_packages

setup(
    name='zengine',
    version='0.0.8',
    url='https://github.com/zetaops/zengine',
    license='GPL',
    packages=find_packages(exclude=['tests', 'tests.*']),
    author='Evren Esat Ozkan',
    author_email='evrenesat@zetaops.io',
    description='A webframework based on SpiffWorkflow (BPMN Engine)',
    install_requires=['beaker', 'falcon', 'beaker_extensions', 'redis',
                      'SpiffWorkflow', 'pyoko', 'passlib'],
    dependency_links=[
        'git+https://github.com/didip/beaker_extensions.git#egg=beaker_extensions',
        'git+https://github.com/zetaops/SpiffWorkflow.git#egg=SpiffWorkflow',
        'git+https://github.com/zetaops/pyoko.git#egg=pyoko',
        ],
)

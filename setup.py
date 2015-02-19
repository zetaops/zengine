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
    description='Minimal BPMN Workflow engine implementation using SpiffWorkflow',
    requires=['SpiffWorkflow'],

)

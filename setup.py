from setuptools import setup

setup(name='yp',
      version='0.1',
      description='A reverse debugger for python',
      author='Manuel Schölling',
      author_email='manuel.schoelling@gmx.de',
      license='GPL',
      packages=['yp'],
      install_requires = [],
      scripts=['bin/yp'],
      zip_safe=False)

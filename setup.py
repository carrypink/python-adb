#!/usr/bin/env python3
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor Boston, MA 02110-1301, USA

# Copyright 2013 Andy Holmes <andrew.g.r.holmes@gmail.com>

"""adb install script."""


from setuptools import setup


def readme():
    with open('README.rst') as readme:
        return readme.read()


setup(name='adb',
      version='0.1',
      description='Python3 Module for the Android Debugging Bridge',
      long_description=readme(),
      classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Other Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.3',
        'Topic :: Software Development :: Debuggers',
        'Topic :: System :: Recovery Tools'
      ],
      keywords='android adb',
      url='http://github.com/andyholmes/python-adb',
      author='Andy Holmes',
      author_email='andrew.g.r.holmes@gmail.com',
      license='GPLv3',
      packages=['adb'],
      #scripts=['bin/adb'],
      #install_requires=['gi.repository'],
      zip_safe=False)

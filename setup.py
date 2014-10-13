#!/usr/bin/env python

from setuptools import setup
import glob

setup(name='dva',
    version='0.1',
    description="dva's validation. again.",
    author='dparalen',
    author_email='vetrisko@gmail.com',
    url='https://github.com/RedHatQE/dva',
    license="GPLv3+",
    provides='dva',
    install_requires=['PyYAML', 'aaargh', 'stitches>=0.7', 'boto'],
    packages=[
        'dva', 'dva.test', 'dva.cloud', 'dva.work', 'dva.tools', 'dva.connection', 'dva.report'
        ],
    data_files=[
             ('/usr/share/dva/hwp', glob.glob('hwp/*.yaml')),
             ('/usr/share/dva/data', glob.glob('data/*')),
             ('/usr/share/dva/examples', glob.glob('examples/*.yaml')),
             ('/etc', ['etc/dva.yaml']),
             ('/etc/bash_completion.d/', ['etc/bash_completion.d/dva'])
    ],
    classifiers=[
            'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
            'Programming Language :: Python',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Operating System :: POSIX',
            'Intended Audience :: Developers',
            'Development Status :: 4 - Beta'
    ],
    scripts=['scripts/dva'],
)

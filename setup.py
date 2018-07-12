from setuptools import setup
import os

def readme():
    with open('README.rst') as f:
        return f.read()

def version():
    version_file = 'mypsl/lib/_version.py'
    if os.path.isfile(version_file):
        exec (open(version_file).read())
        return __version__
    else:
        return 'unknown'

setup(
    name='mypsl',
    version=version(),
    description='Whittling down the MySQL process list',
    long_description=readme(),
    url='https://github.com/ksgh/mypsl',
    author='Kyle Shenk',
    author_email='k.shenk@gmail.com',
    license='MIT',
    packages=['mypsl'],
    install_requires=[
        'colorama',
        'argparse',
        'argcomplete',
        'pymysql'
    ],
    zip_safe=False,

    entry_points={
        'console_scripts': ['mypsl=mypsl:main'],
    },
    classifiers={
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7'
    }
)
from setuptools import setup, find_packages

def readme():
    with open('README.rst') as f:
        return f.read()

def get_version():
    version_file = 'mypsl/libs/_version.py'
    exec (open(version_file).read())
    return __version__

setup(
    name='mypsl',
    version=get_version(),
    description='Whittling down the MySQL process list',
    long_description=readme(),
    url='https://github.com/ksgh/mypsl',
    author='Kyle Shenk',
    author_email='k.shenk@gmail.com',
    license='MIT',
    packages=find_packages(),
    install_requires=[
        'colorama',
        'argparse',
        'argcomplete',
        'pymysql',
        'slackclient'
    ],
    zip_safe=False,

    entry_points={
        'console_scripts': ['mypsl=mypsl.cli:main'],
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
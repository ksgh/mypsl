from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

setup(
    name='mypsl',
    version='0.2',
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
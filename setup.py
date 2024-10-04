from setuptools import find_packages, setup


def read_requirements(file):
    with open(file, encoding='utf-8') as f:
        return f.read().splitlines()


def read_file(file):
    with open(file, encoding='utf-8') as f:
        return f.read()


version = read_file('VERSION')
requirements = read_requirements('requirements.txt')

setup(
    name='schedulebot',
    version=version,
    author='Oleksandr Anosov',
    description='A simple example python package.',
    license='MIT license',
    packages=find_packages(
        exclude=['test']
    ),  # Don't include test directory in binary distribution
    install_requires=requirements,
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],  # Update these accordingly
)

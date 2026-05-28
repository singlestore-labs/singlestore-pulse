from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name='singlestore_pulse',
    version='0.4.10',
    packages=find_packages(),
    description='Singlestore Python SDK for OpenTelemetry Integration',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    install_requires=requirements,
    author='Ashutosh Anshu',
    author_email='aanshu@singlestore.com',
    classifiers=[
        'Programming Language :: Python :: 3.12',
    ],
)

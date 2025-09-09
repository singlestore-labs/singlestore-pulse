#!/bin/bash
set -e

python3 setup.py sdist bdist_wheel
pip uninstall singlestore_pulse -y
pip install dist/singlestore_pulse-0.4.2-py3-none-any.whl
# pytest -v --tb=short

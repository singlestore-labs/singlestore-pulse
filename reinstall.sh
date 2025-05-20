#!/bin/bash
set -e

pytest -v --tb=short
python3 setup.py sdist bdist_wheel
pip uninstall singlestore_pulse -y
pip install dist/singlestore_pulse-0.1-py3-none-any.whl

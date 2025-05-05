## Building the Package

Navigate to the root directory of your project and run the following command to build your package:
```bash
python3 setup.py sdist bdist_wheel
```

Make sure `setuptools` and `wheel` are installed:
```bash
pip install --upgrade setuptools wheel
```

## Testing Locally

After building, you can install the package locally using:
```bash
pip install dist/singlestore_pulse-0.1-py3-none-any.whl
```

## Running unit tests locally

To run the unit tests, use the following command in parent directory of the singlestore_pulse project:
```bash
pytest -v --tb=short
```
This will execute all the tests in the `tests` directory and provide a verbose output with a short traceback for any failures.

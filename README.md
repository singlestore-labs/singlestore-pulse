# singlestore-pulse

SingleStore Python SDK for OpenTelemetry integration. Distributed as `singlestore_pulse`,
imported as `pulse_otel`.

## Installation

```bash
pip install git+https://github.com/singlestore-labs/singlestore-pulse.git@v0.4.14
```

## Development

Tooling is driven by [uv](https://docs.astral.sh/uv/) and `make`.

```bash
make install-dev   # uv sync --all-groups
make check         # format-check + lint-check + test
make test          # run the test suite
make lint-fix      # apply ruff lint fixes
make format-fix    # apply ruff formatting
make build         # build sdist + wheel into dist/
```

## Releasing

Releases are cut from `master` and published as GitHub releases (git tags `vX.Y.Z`, no PyPI):

```bash
make release                 # interactive: prompts for patch/minor/major
make release VERSION=0.4.15  # non-interactive
```

This bumps `src/pulse_otel/version.py`, opens a release PR, and on merge the
`python-release.yml` workflow tags `vX.Y.Z` and creates the GitHub release.

# DSP Mock Package

![PyPI version](https://img.shields.io/pypi/v/nextdep_dsp.svg)

Prepares data to be deposited into OneDep system through the Deposition API.

## Authentication

This package requires a OneDep API JWT to authenticate with the deposition API. The token can be provided in one of two ways:

**File (default):** Store the JWT in `~/.onedepapi.jwt`. The file should contain only the token string (plain text, no quotes).

```bash
echo "your.jwt.token" > ~/.onedepapi.jwt
```

**Environment variable:** Set the `ONEDEP_API_KEY` environment variable.

```bash
export ONEDEP_API_KEY="your.jwt.token"
```

The package prefers the file by default. You can also use the helper to store the token programmatically:

```python
from nextdep_dsp.authorization.token import set_api_key

set_api_key("your.jwt.token")
```

## Features

* TODO

## Documentation

Documentation is built with [Zensical](https://zensical.org/) and deployed to GitHub Pages.

<!-- * **Live site:** https://wmorellato.github.io/nextdep_dsp/ -->
* **Preview locally:** `just docs-serve` (serves at http://localhost:8000)
* **Build:** `just docs-build`

API documentation is auto-generated from docstrings using [mkdocstrings](https://mkdocstrings.github.io/).

Docs deploy automatically on push to `main` via GitHub Actions. To enable this, go to your repo's Settings > Pages and set the source to **GitHub Actions**.

## Development

To set up for local development:

```bash
# Clone your fork
git clone git@github.com:your_username/nextdep_dsp.git
cd nextdep_dsp

# Install in editable mode with live updates
uv tool install --editable .
```

This installs the CLI globally but with live updates - any changes you make to the source code are immediately available when you run `nextdep_dsp`.

Run tests:

```bash
uv run pytest
```

Run quality checks (format, lint, type check, test):

```bash
just qa
```

## Author

- Weslley [...]
- James [...]

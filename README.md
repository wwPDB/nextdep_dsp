# DSP Mock Package

![PyPI version](https://img.shields.io/pypi/v/nextdep_dsp.svg)

Prepares data to be deposited into OneDep system through the Deposition API.

## Configuration

`DepositApi` resolves its settings from three sources in order of increasing priority:

1. `~/.config/nextdep/config.toml` (lowest — persistent dev defaults)
2. Environment variables (override file — useful for CI/pipelines)
3. Constructor arguments (highest — always win)

### Config file

Create `~/.config/nextdep/config.toml`:

```toml
[default]
api_key = "your.jwt.token"
hostname = "https://onedep-depui-test.wwpdb.org/deposition"
ssl_verify = false
redirect = true
```

Once set, instantiate with no arguments:

```python
from nextdep_dsp.deposition.deposit_api import DepositApi

api = DepositApi()  # reads from config file
```

### Environment variables

| Variable | Setting | Type |
|---|---|---|
| `ONEDEP_API_KEY` | API JWT token | str |
| `ONEDEP_HOSTNAME` | Deposition site URL | str |
| `ONEDEP_SSL_VERIFY` | SSL verification | `true`/`false` |
| `ONEDEP_REDIRECT` | Follow site redirects | `true`/`false` |

```bash
export ONEDEP_API_KEY="your.jwt.token"
export ONEDEP_HOSTNAME="https://onedep-depui-test.wwpdb.org/deposition"
export ONEDEP_SSL_VERIFY="false"
```

### Constructor arguments

Constructor arguments always take precedence over all other sources:

```python
api = DepositApi(
    hostname="https://onedep-depui-test.wwpdb.org/deposition",
    api_key="your.jwt.token",
    ssl_verify=False,
)
```

> **Note:** `DepositApi()` raises `DepositApiException` immediately at instantiation if no `api_key` is configured from any source.

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

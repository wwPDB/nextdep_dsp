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

## Using DepositAPI

To create depositions, use the helper methods in `DepositApi`. The example below shows how to create an XRays and EM depositions. Use the enumerations provided in this package to use the APIs.

```python
# XRAY

api = DepositApi() # parameters will be read from the config file
deposition = api.create_xray_deposition(email="wbueno@ebi.ac.uk", users=["0000-0002-5109-8728"], country=Country.USA)
dep_id = deposition.dep_id

file1 = api.upload_file(dep_id=dep_id, file_path="/.../test_files/xray/2gc2.cif",
                        file_type=FileType.MMCIF_COORD)
file2 = api.upload_file(dep_id=dep_id, file_path="/.../test_files/xray/2gc2-sf.cif",
                        file_type=FileType.CRYSTAL_STRUC_FACTORS)

status = api.process(dep_id=dep_id)
while status.status != "finished":
    print(f"Deposition {dep_id} status: {status.status}")
    time.sleep(15)
    status = api.get_status(dep_id=dep_id)

# EM

deposition = api.create_em_deposition(
    email="wbueno@ebi.ac.uk",
    users=["0000-0001-6872-1814"],
    country=Country.USA,
    subtype=EMSubType.SPA,
    coordinates=True
)
dep_id = deposition.dep_id

api.upload_file(dep_id=dep_id, file_path="/.../test_files/em/emd_33233.cif",
                    file_type=FileType.MMCIF_COORD)
api.upload_file(dep_id=dep_id, file_path="/.../test_files/em/emd_33233.map.gz",
                    file_type=FileType.EM_MAP)
api.upload_file(dep_id=dep_id, file_path="/.../test_files/em/emd_33233_half_map_1.map.gz",
                    file_type=FileType.EM_HALF_MAP)
api.upload_file(dep_id=dep_id, file_path="/.../test_files/em/emd_33233_half_map_2.map.gz",
                    file_type=FileType.EM_HALF_MAP)
api.upload_file(dep_id=dep_id, file_path="/.../test_files/em/emd_33233.png",
                    file_type=FileType.ENTRY_IMAGE)
...
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

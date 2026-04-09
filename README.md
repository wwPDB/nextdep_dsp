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

## DSP API

The DSP (Deposition Software Provider) API is the high-level interface for third-party suites (CCP4, Phenix, GlobalPhasing) to stage files locally, run pre-submission checks, and submit depositions to OneDep. It persists session state in a local SQLite database so workflows can be interrupted and resumed.

### New deposition

```python
import nextdep_dsp as dsp

with dsp.deposit_init(
    email="depositor@example.org",
    users=["0000-0002-5109-8728"],   # ORCID IDs
    country=dsp.Country.USA,
    experiment_type=dsp.ExperimentType.XRAY,
) as dep:
    print(dep.session_id)           # save this to resume later

    coord_id = dep.add_file("model.cif",   dsp.FileType.MMCIF_COORD)
    sf_id    = dep.add_file("data-sf.cif", dsp.FileType.CRYSTAL_STRUC_FACTORS)

    report = dep.check_required_files()
    if not report.ok:
        for issue in report.errors():
            print(issue.message)

    dep_id = dep.deposit()          # non-blocking; triggers upload + process
    print(dep.get_status())
```

See [`examples/xray_deposition.py`](examples/xray_deposition.py) for a complete walkthrough including per-file checks.

### Resume an existing session

Sessions are identified by a UUID printed at creation time. Pass it to `deposit_resume()` to reload the full session state — registered files and remote deposition ID included.

```python
dep = dsp.deposit_resume("your-session-uuid")

dep.add_file("extra.cif", dsp.FileType.CRYSTAL_STRUC_FACTORS)
dep.deposit()   # reuses the existing remote deposition if already submitted
```

See [`examples/resume_deposition.py`](examples/resume_deposition.py) for a complete example.

### List all sessions

```bash
nextdep_dsp sessions list
```

Displays a table of all local sessions with their metadata and registered files:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Session ID                           ┃ Created          ┃ Email                 ┃ Experiment ┃ Remote dep ID ┃ Files                          ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 051dcbe3-59c7-4cf8-8af9-675f375b82ae │ 2026-04-08 11:33 │ depositor@example.org │    xray    │   D_800279    │ 2gc2.cif  co-cif               │
│                                      │                  │                       │            │               │ 2gc2-sf.cif  xs-cif            │
└──────────────────────────────────────┴──────────────────┴───────────────────────┴────────────┴───────────────┴────────────────────────────────┘
```

Sessions with no `Remote dep ID` have not been submitted yet. Pass `--base-dir` to inspect sessions stored in a non-default location.

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

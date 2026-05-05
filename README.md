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

Or run the command line tool:

```bash
nextdep_api_token set-api-key your.jwt.token
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

## DSP API

The DSP (Deposition Software Provider) API is the high-level interface for third-party suites (CCP4, Phenix, GlobalPhasing) to stage files locally, run pre-submission checks, and submit depositions to OneDep. It persists session state in a local JSON file so workflows can be interrupted and resumed.

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

```python
with dsp.deposit_init(
    email="depositor@example.org",
    users=["0000-0002-5109-8728"],   # ORCID IDs
    country=dsp.Country.USA,
) as dep:
    dep.set_experiment_type(dsp.ExperimentType.EM)
    dep.set_em_params(em_subtype=dsp.EMSubType.SPA, coordinates=True)

    coord_id = dep.add_file('emd_33233.cif',   dsp.FileType.MMCIF_COORD)
    map_id = dep.add_file('emd_33233.map.gz',     dsp.FileType.EM_MAP)
    half1_id = dep.add_file('emd_33233_half_map_1.map.gz',   dsp.FileType.EM_HALF_MAP)
    half2_id = dep.add_file('emd_33233_half_map_2.map.gz',   dsp.FileType.EM_HALF_MAP)
    dep.add_file('emd_33233.png',   dsp.FileType.ENTRY_IMAGE)
    dep.check_required_files()

    dep.set_voxel_values(map_id,   spacing_x=1.0825, spacing_y=1.0825, spacing_z=1.0825, contour=0.01)
    dep.set_voxel_values(half1_id, spacing_x=1.0825, spacing_y=1.0825, spacing_z=1.0825, contour=0.01)
    dep.set_voxel_values(half2_id, spacing_x=1.0825, spacing_y=1.0825, spacing_z=1.0825, contour=0.01)
    dep.check_file_type(fsc_xml_id, dsp.FileType.FSC_XML)
    dep.deposit()
    dep.get_status()
```

See [`examples/em_deposition.py`](examples/em_deposition.py) for a complete walkthrough including per-file checks.

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

For an end-to-end CLI flow (no Python required), see the [Command-line walkthrough](#command-line-walkthrough) section below.

## Command-line walkthrough

This section walks through a complete X-ray deposition against the OneDep test
endpoint using only CLI commands. The starting position is "fresh `git clone`,
nothing else"; the inputs you need are:

* a depositor email
* an ORCID iD
* a JWT API key
* a coordinate mmCIF file (e.g. `model.cif`)
* a reflection-data mmCIF file (e.g. `data.cif`)

The walkthrough talks to the wwPDB OneDep **test** endpoint. Switch to
production by changing `hostname` in the config below.

### What's CLI-native vs Python-only

The CLI exposes the full submission cycle (create / upload / process / status)
plus a schema-level pre-flight (`nextdep_schema_compliance filecheck`). The
deeper file-content validation provided by the DSP API
(`check_mmcif_file`, `check_mmcif_category`, `check_mmcif_field`,
`check_file_type`) is currently Python-only — see
[`examples/xray_deposition.py`](examples/xray_deposition.py) for that flow.

### 1. Install

See [Development](#development) below for the full clone+install commands. After
`uv tool install --editable .`, three CLI entry points are on `PATH`:
`nextdep_dsp`, `nextdep_schema_compliance`, `nextdep_api_token`.

### 2. Configure the API key and the test endpoint

Create `~/.config/nextdep/config.toml` with your JWT token. Pointing at the
test endpoint avoids polluting the production archive while you exercise the
flow:

```toml
[default]
api_key = "your.jwt.token"
hostname = "https://onedep-depui-test.wwpdb.org/deposition"
ssl_verify = false
redirect = true
```

Or set the equivalent environment variables (overrides the file):

```bash
export ONEDEP_API_KEY="your.jwt.token"
export ONEDEP_HOSTNAME="https://onedep-depui-test.wwpdb.org/deposition"
export ONEDEP_SSL_VERIFY="false"
```

#### A note on test-endpoint routing

The wwPDB routes incoming depositions to one of three deposit sites
(RCSB, PDBe, PDBj) based on the depositor's country, ORCID, and
similar metadata. The `onedep-depui-test.wwpdb.org` endpoint above is
the **RCSB-side test cluster** — it accepts only depositions that the
routing rules send to RCSB.

If your live affiliation routes you to PDBe or PDBj, `nextdep_dsp
create` against this endpoint will fail with an `invalid_location`
error pointing at the corresponding production deposit site. Two
paths forward:

1. Use `country = "United States"` for the duration of the test. The
   routing decision is made on the country field, so this lands the
   deposition on the RCSB test cluster. Restore your real country
   before any real submission.
2. Coordinate with your wwPDB site contact about whether a PDBe or
   PDBj test endpoint is available, and if so, point `hostname` in
   the config file to it.

The `redirect = true` flag in the config example above attempts to
follow such routing suggestions automatically, but the suggested
target is normally a production endpoint. While testing, prefer
`redirect = false` so a routing rejection surfaces as a clear error
instead of being silently re-routed to production.

### 3. Pre-flight check (schema-level)

Before talking to the server, confirm that the file types you intend to
upload satisfy the X-ray experiment's required-files schema:

```bash
nextdep_schema_compliance filecheck xray \
    --filetype co-cif \
    --filetype xs-cif
```

A successful check prints `validated correctly`. The wire-format codes for
the file types are:

| You have                 | Use this code |
|--------------------------|---------------|
| coordinates in mmCIF     | `co-cif`      |
| coordinates in PDB       | `co-pdb`      |
| reflection data in mmCIF | `xs-cif`      |
| reflection data in MTZ   | `xs-mtz`      |

This check is structural — it confirms the *list* of file types is valid for
the experiment. It does not parse the actual files.

### 4. Create a remote deposition

```bash
nextdep_dsp create xray you@example.org "United States" \
    --user 0000-0001-2345-6789
```

`exptype`, `email`, and `country` are positional; `--user` is repeatable
for additional ORCID iDs. The country string must match a name in the
wwPDB enumeration list (run `nextdep_dsp create --help` for hints, or see
the `Country` enum). On success the command prints the new deposition ID
(e.g. `D_8000000123`); take note of it for the remaining steps.

### 5. Upload your files

Two uploads, one per file. Pass the deposition ID, the file path, and the
file-type code from the table above:

```bash
nextdep_dsp upload D_8000000123 /path/to/model.cif co-cif
nextdep_dsp upload D_8000000123 /path/to/data.cif  xs-cif
```

Each successful upload prints the file id assigned by the server.

### 6. Trigger processing

```bash
nextdep_dsp process D_8000000123
```

This kicks off server-side processing of the uploaded files. The command
returns immediately; processing runs asynchronously.

### 7. Poll for status

```bash
nextdep_dsp status D_8000000123
```

Re-run as desired. Processing typically takes seconds to a few minutes.

### Inspecting the deposition

A few helpers for after the fact:

```bash
nextdep_dsp get-deposition D_8000000123      # full deposition record
nextdep_dsp get-files      D_8000000123      # listing of uploaded files
nextdep_dsp get-users      D_8000000123      # access list
```

### What the CLI does NOT cover

* Local session bookkeeping (file MD5s, atomic JSON state, session resume
  by UUID). That lives in the Python DSP API.
* File-content validation (`check_mmcif_*`, `check_file_type`). Also Python
  only.

If either of those matters to you — e.g. a long upload that you may need
to resume, or a strict pre-flight that opens the CIF and verifies
required categories — use the Python flow shown in the
[DSP API](#dsp-api) section above.

## Features

* Test required files

```bash
nextdep_schema_compliance filecheck <exptype> --filetype <type> --filetype <type> ...
```

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
# Clone the repository (replace `wwPDB` with your fork's owner if you forked)
git clone https://github.com/wwPDB/nextdep_dsp.git
cd nextdep_dsp

# Install in editable mode with live updates. Requires `uv`
# (https://docs.astral.sh/uv/getting-started/installation/) — if not present:
#   curl -LsSf https://astral.sh/uv/install.sh | sh
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

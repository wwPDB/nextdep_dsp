# DSP API Internals

How the DSP public API works under the hood — session storage, identifiers, file handling, and the submission flow.

---

## Architecture overview

```
Third-party code
      │
      ▼
  Deposition          ← public facade  (src/nextdep_dsp/dsp.py)
      │
      ├── SessionStore  ← SQLite CRUD   (src/nextdep_dsp/session/store.py)
      │       └── ~/.nextdep/sessions/<session_id>/session.db
      │
      └── DepositApi    ← REST client   (src/nextdep_dsp/deposition/deposit_api.py)
              └── https://onedep-depui-test.wwpdb.org/deposition/api/v1/
```

The `Deposition` facade is the only thing callers interact with. It delegates persistence to `SessionStore` and remote API calls to `DepositApi`.

---

## Identifiers

Two distinct IDs are in play:

| ID | Type | Created by | Stored in | Purpose |
|----|------|------------|-----------|---------|
| `session_id` | UUID v4 | `deposit_init()` | SQLite + in-memory | Identifies the local session (before and after remote submission) |
| `file_id` | UUID v4 | `add_file()` | SQLite | Opaque handle for a registered file; passed to check methods |
| `remote_dep_id` | String (e.g. `D_8000000001`) | OneDep API on `deposit()` | SQLite (`sessions.remote_dep_id`) | Identifies the deposition on the remote server |

`remote_dep_id` starts as `None` and is written to the database as the **first thing** after the remote deposition is created — before any file uploads — so it survives a crash mid-upload. If you see a session with a `remote_dep_id` but no files uploaded, the deposition exists on the server and can be managed via the DepUI.

---

## Session storage

Each call to `deposit_init()` creates an isolated directory:

```
~/.nextdep/sessions/
└── <session_id>/
    └── session.db        ← SQLite database for this session
```

The base path can be overridden with the `_base_dir` parameter (used in tests).

### SQLite schema

**`sessions` table** — one row per session:

| Column | Type | Notes |
|--------|------|-------|
| `session_id` | TEXT PK | UUID v4 |
| `email` | TEXT | Depositor email |
| `users` | TEXT | JSON array of ORCID IDs |
| `country` | TEXT | `Country` enum value |
| `experiment_type` | TEXT | `ExperimentType` enum value; nullable |
| `created_at` | TEXT | ISO 8601 timestamp |
| `db_path` | TEXT | Absolute path to this database file |
| `remote_dep_id` | TEXT | Set after `deposit()` succeeds; nullable |

**`files` table** — one row per registered file:

| Column | Type | Notes |
|--------|------|-------|
| `file_id` | TEXT PK | UUID v4 |
| `session_id` | TEXT FK | References `sessions.session_id` |
| `file_path` | TEXT | Absolute path on local disk |
| `file_type` | TEXT | `FileType` enum value (e.g. `co-cif`) |

`users` is stored as a JSON array because SQLite has no native array type.

---

## File handling

`add_file(file_path, file_type)` resolves the path to an absolute path and stores it — **no copy is made**. The file must remain at that location until `deposit()` completes.

`remove_file(file_id)` deletes the row from the `files` table. The file on disk is untouched. Raises `KeyError` if `file_id` is not found.

Files are uploaded to the remote API during `deposit()`, in the order they were added.

---

## Submission flow (`deposit()`)

```
deposit()
  │
  ├─ guard: experiment_type must be set
  │
  ├─ if remote_dep_id is None:  (first submission)
  │     DepositApi.create_deposition()  → dep_id
  │     SessionStore.set_remote_dep_id(dep_id)   ← persisted before uploads
  │
  └─ else:  (re-submission — remote deposition already exists)
        reuse existing remote_dep_id
  │
  ├─ for each file currently in session:
  │     DepositApi.upload_file(dep_id, file_path, file_type)
  │
  ├─ DepositApi.process(dep_id)
  │
  └─ return dep_id  (non-blocking — processing continues server-side)
```

`deposit()` can be called more than once on the same session. On the second call it skips deposition creation and uploads all currently registered files to the existing remote deposition, then triggers processing again. This is the intended flow for adding files incrementally.

`deposit()` returns as soon as `process()` is called. The caller should poll `get_status()` to track progress.

`get_status()` raises `RuntimeError` if called before `deposit()`.

---

## Check functions

All check functions in `src/nextdep_dsp/checks/file_checks.py` are currently **stubs** — they return an empty `CheckReport` (i.e. `ok=True`, no issues). They accept `file_id` strings; the `Deposition` facade resolves them to `LocalFile` objects via `SessionStore.get_file()` before passing them down.

`CheckReport.ok` is `True` when no issue has severity `ERROR` or `FATAL`.

---

## Connection lifecycle

`SessionStore` holds an open `sqlite3` connection for the lifetime of the object. Call `dep.close()` (or use `dep` as a context manager) to release it:

```python
with dsp.deposit_init(...) as dep:
    dep.add_file(...)
    dep.deposit()
# connection closed automatically
```

`get_status()` and `check_auth_key()` each instantiate a short-lived `DepositApi` object per call; they do not hold persistent connections.

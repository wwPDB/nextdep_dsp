# JSON Session Backend

**Date:** 2026-04-10
**Status:** Approved

## Summary

Replace the SQLite3 backend in `SessionStore` with a single JSON file. The public interface stays identical; only the storage mechanism changes.

## Storage Layout

Each session directory already contains one file per session. The SQLite database is replaced 1-for-1:

```
~/.nextdep/sessions/<session_id>/session.json   # was session.db
```

### File Structure

```json
{
  "session": {
    "session_id": "...",
    "email": "...",
    "users": ["..."],
    "country": "US",
    "experiment_type": "EM",
    "created_at": "2026-04-10T12:00:00",
    "db_path": "/home/user/.nextdep/sessions/.../session.json",
    "remote_dep_id": null,
    "em_subtype": null,
    "coordinates": null
  },
  "files": {
    "<file_id>": {
      "file_id": "...",
      "session_id": "...",
      "file_path": "/path/to/file.cif",
      "file_type": "co",
      "voxel": null
    }
  }
}
```

All values use the same serialisation as before (enum `.value`, `datetime.isoformat()`, etc.).

## SessionStore Changes

### Internal state

- `self._json_path: Path` — path to `session.json` (replaces `self._db_path`)
- `self._data: dict` — in-memory document `{"session": ..., "files": {...}}`

### Initialisation

- If `session.json` exists: load it into `self._data`
- If not: initialise `self._data = {"session": None, "files": {}}`
- No migration logic needed

### `_save()` (private)

Atomic write: serialize `self._data` to `session.json.tmp`, then `os.replace()` to `session.json`.

### Public method behaviour

| Method | Change |
|---|---|
| `create_session` | Sets `self._data["session"]`, calls `_save()` |
| `get_session` | Reads from `self._data["session"]`; raises `KeyError` if `None` |
| `update_experiment_type` | Mutates `self._data["session"]`, calls `_save()` |
| `update_em_params` | Mutates `self._data["session"]`, calls `_save()` |
| `set_remote_dep_id` | Mutates `self._data["session"]`, calls `_save()` |
| `add_file` | Inserts into `self._data["files"]`, calls `_save()` |
| `set_voxel_values` | Updates file entry in `self._data["files"]`, raises `KeyError` if absent, calls `_save()` |
| `remove_file` | Deletes from `self._data["files"]`, raises `KeyError` if absent, calls `_save()` |
| `get_file` | Reads from `self._data["files"]`, raises `KeyError` if absent |
| `get_all_files` | Returns all values from `self._data["files"]` filtered by `session_id` |
| `close` | No-op |

### `db_path` property

Returns `self._json_path`. Callers that store `str(store.db_path)` in `LocalSession.db_path` will now store the `.json` path — correct behaviour.

## dsp.py Changes

`list_depositions` currently probes `entry / "session.db"` to detect valid sessions. Change to `entry / "session.json"`.

## What Is Removed

- All SQLite DDL strings (`_CREATE_SESSIONS`, `_CREATE_FILES`)
- The `_MIGRATIONS` list and migration loop
- The `sqlite3` import
- `self._conn`

## Testing

Existing tests in `tests/session/test_store.py` require no interface changes. The `tmp_path` fixture already isolates storage, so tests will exercise the JSON backend transparently.

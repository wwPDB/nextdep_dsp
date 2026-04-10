# File Metadata (MD5 + mtime) Design

**Date:** 2026-04-10
**Status:** Approved

## Summary

Store each registered file's MD5 checksum and disk mtime alongside existing file metadata. Update the `sessions list` CLI command to remove the email column and display per-file md5 (truncated), path, and mtime.

## Data Model

`LocalFile` gains two optional fields:

```python
md5: str | None = None           # 32-char hex string
file_mtime: datetime | None = None  # UTC datetime from Path.stat().st_mtime
```

Fields are optional so existing sessions missing these keys deserialise without error.

## Computation

Both values are computed eagerly in `Deposition.add_file()` (in `src/nextdep_dsp/dsp.py`), immediately after the file existence check:

```python
stat = path.stat()
file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
md5 = hashlib.md5(path.read_bytes()).hexdigest()
```

`hashlib` is stdlib — no new dependency.

## Storage

The JSON `files` dict entry gains two keys:

```json
{
  "file_id": "...",
  "session_id": "...",
  "file_path": "...",
  "file_type": "...",
  "voxel": null,
  "md5": "a3f1c9d2e8b74f01c5e2d3a9b8f7c601",
  "file_mtime": "2026-04-10T09:12:00+00:00"
}
```

`file_mtime` serialises as `datetime.isoformat()` and deserialises with `datetime.fromisoformat()`. Sessions written before this change have `null` for both fields — no migration needed.

## CLI Changes

`sessions list` (`src/nextdep_dsp/cli.py`):

- Remove the `Email` column
- The `Files` column shows one line per file:
  `<md5[:8]>  <full path>  <mtime formatted as %Y-%m-%d %H:%M>`
- If `md5` or `file_mtime` is `None` (legacy session): show `[dim]-[/dim]` in place of the missing value

Example files cell:
```
a3f1c9d2  /data/model.cif  2026-04-10 09:12
d84b2e11  /data/map.mrc    2026-04-09 14:30
```

## Files Changed

| File | Change |
|---|---|
| `src/nextdep_dsp/session/models.py` | Add `md5` and `file_mtime` fields to `LocalFile` |
| `src/nextdep_dsp/session/store.py` | Serialise/deserialise new fields |
| `src/nextdep_dsp/dsp.py` | Compute md5 and mtime in `add_file()` |
| `src/nextdep_dsp/cli.py` | Remove email column; update files column |

# SQLite snapshot validation — security milestone

This utility uses SQLite's online backup API rather than copying a hot WAL-backed DB file. It creates a separate file without overwriting existing snapshots, then checks `PRAGMA integrity_check`, checkpoint schema, JSON readability and session identity; it reports only a SHA-256 digest and counts. The **source** is read-only. A snapshot that fails validation is deleted, not passed to recovery.

```bash
# Run in an isolated, authorized environment after arranging a destination:
python -m recovery --source /data/sessions.sqlite3 --snapshot /secure-export/checkpoint-20261029.sqlite3
# Later, after separately obtaining a restored copy:
python -m recovery --snapshot /isolated-restore/checkpoint-20261029.sqlite3
```

**NOT A COMPLETED P0 BACKUP:** Snapshots created on the same Railway volume, or on transient service storage, are not independent or durable. This utility does **not** encrypt files, replicate backups off-site, configure schedules/retention, validate every model's semantics, or demonstrate RPO/RTO. No command here restores the running production volume. Do not upload any plaintext snapshot to public or unsecured storage.

Railway [volume backups](https://docs.railway.com/volumes/backups) are available, but the documented restore is same-project and same-environment; treat it as rapid local rollback, not independent disaster recovery. The full G-04 gate requires an approved encrypted off-project backup destination, off-site keys, independent restore and completed human-reviewed exercise before release qualification.

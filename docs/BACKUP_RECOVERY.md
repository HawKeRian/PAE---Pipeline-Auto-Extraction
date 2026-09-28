# Backup and Recovery Procedure

Create a quiesced, verified archive (or stop writes for the local MVP):

```text
python scripts/backup.py --database data/pae.sqlite3 --samples data/samples --artifacts generated --output backups/pae.zip
```

The command uses SQLite's backup API, hashes every database/sample/artifact entry, excludes `.env`
and secret values, and writes atomically. Store the archive on encrypted media with access controls
and retention aligned to the source-data policy.

Restore only into empty paths:

```text
python scripts/restore.py --archive backups/pae.zip --database restore/pae.sqlite3 --samples restore/samples --artifacts restore/generated
```

Restore verifies paths, sizes, SHA-256 hashes, entry set, and SQLite `integrity_check`. Then start the
same release version, call `/ready`, run the smoke test, authenticate, open a known project, and
download a known artifact. A failed verification is terminal: quarantine the archive and use the
previous known-good backup.

# Baseline decisions

- Record the already-live ladder; do not replay its migration.
- Treat unexpected active or behavior-changing state as failure; dormant unrelated extras are warnings and are never removed automatically.
- Keep rollback snapshots outside Git.
- This repository has no remote until a separately approved action adds one.
- There is no executable apply-state script.

# Domain sync owner cutover evidence — 2026-08-27

## Result: PASS

- backup: `.omo/evidence/20260827T154707Z-governance-state-mutation-49292324/crontab-before.txt`
- backup SHA-256: `a070586211f8c525f1b7da0b4cc702e5ee6dad694c1182c6287f26c60f145f65`
- old `0 6 * * * ... domain-sync.py` count after cutover: 0;
- new accepted-release `documents-domain-index.py check` count: 1;
- unrelated lines: 108, byte-identical;
- after SHA-256: `d188e5a7946ab61979aaa6e86a51077ce04b31f86a1202fa1505850a8f1f41a3`;
- old `/usr/bin/python3` command exit: 1 (`dataclass(slots=True)` on Python 3.9);
- new `uv` accepted-release command exit: 0;
- Documents `DOMAIN-INDEX.md` was read only and not modified by the check;
- rollback: restore the verified backup after checking its SHA-256.

No other crontab entry, LaunchAgent, Scheduled skill, or Documents content was
changed.

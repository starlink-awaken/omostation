# Closeout — staff group ACE (ADR-0208)

```bash
export OMO_ACL_GROUP=staff OMO_OS_ACL=1
bash bin/gac/omo-acl-ops-window.sh --workspace-root="$HOME/Workspace" --apply --yes --acl
# applied_ok=7 applied_fail=0
ls -led .omo/_delivery
# group:staff + user:xiamingxing
```

sudo `omo-writers` create skipped (no interactive password in agent).

"""Check for services that should be listening but aren't."""

from runtime.i0 import i0_services

svc = i0_services()
down = [s for s in svc if not s.get("port_listening") and (s.get("port") or 0) > 0]
for s in down:
    print(f"{s['name']}:{s['port']} - not listening ({s.get('status', '?')})")

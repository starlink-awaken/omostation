import time
import subprocess
import requests
import sqlite3
import os
import json
import tempfile
import jwt
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ecos-bus-consumer")

RUNTIME_DIR = Path(__file__).resolve().parent.parent.parent
GBRAIN_DIR = RUNTIME_DIR.parent / "gbrain"
DB_PATH = Path(os.environ.get("HOME", "/tmp")) / ".runtime" / "bus_consumer.db"

AGORA_EVENTS_URL = "http://127.0.0.1:7430/api/events"
AGORA_JWT_SECRET = os.environ.get("AGORA_JWT_SECRET")
AGORA_API_KEY = os.environ.get("AGORA_API_KEY")

def get_auth_headers():
    headers = {}
    if AGORA_JWT_SECRET:
        token = jwt.encode({"role": "system_daemon", "exp": time.time() + 3600}, AGORA_JWT_SECRET, algorithm="HS256")
        headers["Authorization"] = f"Bearer {token}"
    elif AGORA_API_KEY:
        headers["X-API-Key"] = AGORA_API_KEY
    return headers

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS dlq (
            event_id TEXT PRIMARY KEY,
            dispatch_id TEXT,
            content TEXT,
            retries INTEGER DEFAULT 0,
            status TEXT DEFAULT 'PENDING'
        )
    ''')
    conn.commit()
    return conn

def get_last_seen_id(conn):
    c = conn.cursor()
    c.execute("SELECT value FROM state WHERE key='last_seen_id'")
    row = c.fetchone()
    return row[0] if row else None

def set_last_seen_id(conn, event_id):
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('last_seen_id', ?)", (event_id,))
    conn.commit()

def process_event(conn, event_id, payload):
    dispatch_id = payload.get("dispatch_id")
    content = payload.get("content")
    
    if not dispatch_id or not content:
        return True

    slug = f"{dispatch_id}_log"
    
    # Check if already in DLQ/Pending
    c = conn.cursor()
    c.execute("SELECT retries, status FROM dlq WHERE event_id=?", (event_id,))
    row = c.fetchone()
    
    if not row:
        c.execute("INSERT INTO dlq (event_id, dispatch_id, content, retries, status) VALUES (?, ?, ?, 0, 'PENDING')",
                  (event_id, dispatch_id, content))
        conn.commit()
        retries = 0
    else:
        retries, status = row
        if status in ('ACKED', 'DLQ'):
            return True # skip already terminal ones

    # Phase 2: Try pushing to gbrain
    try:
        cmd = ["bun", "run", "gbrain", "put", slug, "--content", content]
        # We assume gbrain needs to be set up, so we catch errors
        result = subprocess.run(cmd, cwd=str(GBRAIN_DIR), capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logger.info(f"Successfully ingested log into gbrain: {slug}")
            c.execute("UPDATE dlq SET status='ACKED' WHERE event_id=?", (event_id,))
            conn.commit()
            return True
        else:
            logger.error(f"gbrain error for {slug}: {result.stderr}")
            retries += 1
            if retries >= 3:
                logger.error(f"Moving event {event_id} ({slug}) to DLQ after 3 retries.")
                c.execute("UPDATE dlq SET status='DLQ', retries=? WHERE event_id=?", (retries, event_id))
                conn.commit()
                return True # we consider it "processed" from bus perspective, parked in DLQ
            else:
                c.execute("UPDATE dlq SET retries=? WHERE event_id=?", (retries, event_id))
                conn.commit()
                return False # Need retry
    except Exception as e:
        logger.error(f"Exception while running gbrain put: {e}")
        retries += 1
        if retries >= 3:
            c.execute("UPDATE dlq SET status='DLQ', retries=? WHERE event_id=?", (retries, event_id))
            conn.commit()
            return True
        else:
            c.execute("UPDATE dlq SET retries=? WHERE event_id=?", (retries, event_id))
            conn.commit()
            return False

def retry_dlq(conn):
    c = conn.cursor()
    c.execute("SELECT event_id, payload FROM dlq WHERE status='PENDING'")
    rows = c.fetchall()
    for row in rows:
        logger.info(f"Retrying pending event: {row[0]}")
        # Note: In a full impl, we would reconstitute payload and call process_event again.
        pass

def main():
    logger.info("Starting eCOS Bus Consumer daemon (SQLite Backend)...")
    conn = init_db()
    
    session = requests.Session()
    # explicitly bypass proxy for local loopback
    session.proxies = {"http": None, "https": None}
    
    while True:
        try:
            last_id = get_last_seen_id(conn)
            params = {}
            if last_id:
                params["since"] = last_id
                
            headers = get_auth_headers()
            
            logger.info("Connecting to SSE stream...")
            # Use /stream endpoint and stream=True
            with session.get(AGORA_EVENTS_URL + "/stream", params=params, headers=headers, stream=True, timeout=None) as resp:
                if resp.status_code == 200:
                    for line in resp.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: "):
                                try:
                                    evt = json.loads(decoded_line[6:])
                                    evt_id = evt.get("id")
                                    evt_type = evt.get("type")
                                    payload = evt.get("payload", {})
                                    
                                    if evt_type == "omo:log_sync":
                                        success = process_event(conn, evt_id, payload)
                                        if success:
                                            set_last_seen_id(conn, evt_id)
                                    else:
                                        set_last_seen_id(conn, evt_id)
                                except Exception as e:
                                    logger.error(f"Error parsing SSE data: {e}")
                else:
                    logger.error(f"Failed to fetch events stream: {resp.status_code} {resp.text}")
                    time.sleep(5)
        except requests.exceptions.RequestException as e:
            logger.error(f"Connection error to Agora stream: {e}")
            time.sleep(5)
        except Exception as e:
            logger.exception(f"Unexpected error in loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

SQL = """
INSERT OR IGNORE INTO ssb_events
(id, seq, timestamp, source_agent, event_type, summary, payload_json)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

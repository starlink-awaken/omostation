with open("/Users/xiamingxing/workspace/docs/plans/3y-bet-ledger.yaml", "r") as f:
    text = f.read()

text = text.replace(
"""  pasw_required: false
  risk_level: L2
  human_gate: false""",
"""  pasw_required: false
  depends_on:
  - BET-Y1Q1-T1-08
  risk_level: L2
  human_gate: true"""
)

with open("/Users/xiamingxing/ws-bet-y1q2-t1-20/docs/plans/3y-bet-ledger.yaml", "w") as f:
    f.write(text)

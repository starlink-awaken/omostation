import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "projects" / "omo" / "src"))

from omo.blackboard.ast_scanner import scan_python_file
from omo.blackboard.client import BlackboardClient


def test_ast_breach_and_remediation_cycle():
    # Step 1: Base state
    code_kernel_v1 = """
def authenticate_user(token: str) -> bool:
    \"\"\"Authenticate a user token.\"\"\"
    return len(token) > 5
"""
    code_caller = """
from kernel import authenticate_user

def login_flow():
    ok = authenticate_user("valid_token_123")
    return ok
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        f_kernel = tmp_p / "kernel.py"
        f_caller = tmp_p / "caller.py"
        f_kernel.write_text(code_kernel_v1, encoding="utf-8")
        f_caller.write_text(code_caller, encoding="utf-8")

        # Ingest baseline into blackboard
        syms_v1, _ = scan_python_file(f_kernel, "proj:drill")
        sym_auth = syms_v1[0]
        hash_v1 = sym_auth["signature_hash"]

        bb = BlackboardClient(":memory:")
        bb.batch_upsert_symbols(syms_v1)
        bb.record_ast_call(
            caller_file=str(f_caller),
            caller_symbol="sym:proj:drill:caller::login_flow",
            caller_line=5,
            callee_symbol=sym_auth["symbol_id"],
            expected_hash=hash_v1,
        )

        # Step 2: Agent A breaks the signature (adds mandatory param 'realm')
        code_kernel_v2_broken = """
def authenticate_user(token: str, realm: str) -> bool:
    \"\"\"Authenticate a user token with mandatory realm.\"\"\"
    return len(token) > 5 and realm == "admin"
"""
        f_kernel.write_text(code_kernel_v2_broken, encoding="utf-8")
        syms_v2, _ = scan_python_file(f_kernel, "proj:drill")
        hash_v2 = syms_v2[0]["signature_hash"]

        # Step 3: Blast Radius query -> Intercepted!
        impacts = bb.get_blast_radius(sym_auth["symbol_id"], new_sig_hash=hash_v2)
        assert len(impacts) == 1, "Must catch broken caller"
        assert impacts[0]["caller_file"] == str(f_caller)
        assert impacts[0]["caller_line"] == 5

        # Step 4: Agent A remediates with default backward-compatible param
        code_kernel_v2_fixed = """
def authenticate_user(token: str) -> bool:
    \"\"\"Authenticate a user token with compatibility.\"\"\"
    return len(token) > 5
"""
        f_kernel.write_text(code_kernel_v2_fixed, encoding="utf-8")
        syms_v3, _ = scan_python_file(f_kernel, "proj:drill")
        hash_v3 = syms_v3[0]["signature_hash"]

        # Step 5: Verify re-check -> Clean Pass!
        impacts_fixed = bb.get_blast_radius(sym_auth["symbol_id"], new_sig_hash=hash_v3)
        assert len(impacts_fixed) == 0, "Remediated signature must pass with 0 blast radius"

        bb.close()

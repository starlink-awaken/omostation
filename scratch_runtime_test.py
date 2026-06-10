import sys
import os

# Add runtime project to sys.path so we can import it
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
runtime_src = os.path.join(workspace_root, "projects", "runtime", "src")
sys.path.append(runtime_src)

from runtime.kei_sandbox import enable_sandbox
from runtime.executor.sandbox import Sandbox

def main():
    print("1. Enabling KEI Sandbox...")
    enable_sandbox()
    
    print("\n2. Executing code in Runtime API Sandbox...")
    code = """
print("Hello from the restricted KEI Sandbox environment!")
result = {"status": "success", "message": "Sandbox is functioning properly"}
"""
    # Trigger execution
    res = Sandbox.execute(code)
    
    print(f"\nExecution Success: {res.success}")
    if res.success:
        print(f"Stdout:\n{res.stdout.strip()}")
        print(f"Output object: {res.output}")
        print(f"Duration (ms): {res.duration_ms:.2f}")
    else:
        print(f"Error: {res.error}")
        
    print("\n3. Testing Sandbox isolation (trying to import os)...")
    bad_code = """
import os
result = os.environ
"""
    res_bad = Sandbox.execute(bad_code)
    print(f"Bad execution success: {res_bad.success}")
    print(f"Expected Error: {res_bad.error}")

if __name__ == "__main__":
    main()

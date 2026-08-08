import os
import sys
import time
import shutil
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=".")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    
    base_dir = Path(args.dir) / ".omo" / "_delivery" / "agent-workflows" / "runs"
    if not base_dir.exists():
        print("Found 0 zombie runs")
        return
        
    zombies = []
    now = time.time()
    for run in base_dir.iterdir():
        if run.is_dir():
            if (now - run.stat().st_mtime) > 72 * 3600:
                zombies.append(run)
                
    print(f"Found {len(zombies)} zombie runs")
    if args.apply:
        for z in zombies:
            shutil.rmtree(z)

if __name__ == "__main__":
    main()

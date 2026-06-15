import yaml
from pathlib import Path

def extract_ssot_writeback(omo_dir: Path):
    done_dir = omo_dir / "tasks" / "done"
    if not done_dir.exists():
        return
        
    for task_file in done_dir.glob("*.yaml"):
        try:
            with open(task_file, "r") as f:
                task = yaml.safe_load(f)
        except Exception:
            continue
            
        if not isinstance(task, dict):
            continue
            
        context_uri = task.get("context_uri")
        source_docs = task.get("source_docs", [])
        if not context_uri or not source_docs:
            continue
            
        # To avoid multiple writebacks, check if we already marked it
        if task.get("ssot_written_back"):
            continue
            
        source_file = Path(source_docs[0])
        if not source_file.exists():
            continue
            
        # We append a section to the end of the markdown document
        try:
            with open(source_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n### OMO SSOT Write-back: {task['id']}\n")
                f.write(f"> 任务 `{task['title']}` 已在 OMO 稳态区被标记为 Done。\n")
                f.write(f"> 变更详情见卡片 {task['id']} 或其对应的交付记录。\n")
                f.write(f"> 原始 context_uri: `{context_uri}`\n")
                
            # Mark task as written back
            task["ssot_written_back"] = True
            with open(task_file, "w", encoding="utf-8") as f:
                yaml.dump(task, f, allow_unicode=True, sort_keys=False)
            print(f"✅ SSOT Write-back applied for {task['id']} -> {source_file.name}")
        except Exception as e:
            print(f"⚠️ Failed to write back SSOT for {task['id']}: {e}")

extract_ssot_writeback(Path("/Users/xiamingxing/Workspace/.omo"))

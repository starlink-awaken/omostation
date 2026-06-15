import os
import json
import httpx
from typing import Dict, Any

def extract_tasks_from_pitch(pitch_content: str) -> list[Dict[str, Any]]:
    """
    调用 Gemini API 将 Markdown Pitch 解析为结构化的 OMO 任务列表。
    如果没有 API Key，则回退到 Mock 逻辑。
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("  ⚠️ 未检测到 GEMINI_API_KEY，正在使用 Mock LLM 提取逻辑。")
        return []
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    prompt = f"""
    你是一个 OMO 架构下的首席技术合伙人 (CTO)。
    请阅读下面的点子 (Pitch) 提案，将其拆解为 1-3 个具体的 OMO 执行任务。
    
    必须以 JSON 数组格式返回，每个任务必须包含以下字段：
    - title: 任务标题
    - description: 任务详细描述（包含技术上下文）
    - task_type: "feature" 或 "refactor" 或 "bugfix"
    - risk_level: "L0" 到 "L3" (一般填 L0 或 L1)
    - deliverables: 数组，预期的交付物列表
    - evidence_required: 数组，需要提供的验收证据
    - test_plan: 数组，测试计划
    
    Pitch 提案内容：
    ---
    {pitch_content}
    ---
    
    请严格返回合法的 JSON 数组，不要包含 ```json 等 Markdown 标记，直接返回内容。
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2
        }
    }
    
    try:
        resp = httpx.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        result_text = data["candidates"][0]["content"]["parts"][0]["text"]
        
        # 简单清理可能的 markdown
        result_text = result_text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        tasks = json.loads(result_text)
        if not isinstance(tasks, list):
            tasks = [tasks]
        return tasks
    except Exception as e:
        print(f"  ❌ LLM 请求失败: {e}，回退到 Mock。")
        return []

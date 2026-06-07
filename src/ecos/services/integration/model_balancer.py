MODEL_STATS = {
    "DeepSeek": {"reasoning": 0.72, "cost": 0.35},
    "Qwen": {"reasoning": 0.61, "cost": 0.28},
    "GLM": {"reasoning": 0.56, "cost": 0.24},
}


def get_model_usage(stats: bool = False):
    imbalance = max(v["reasoning"] for v in MODEL_STATS.values()) - min(v["reasoning"] for v in MODEL_STATS.values())
    if stats:
        return MODEL_STATS, imbalance
    return MODEL_STATS


def recommend(task_type: str) -> str:
    if task_type == "reasoning":
        return "DeepSeek"
    return "Qwen"

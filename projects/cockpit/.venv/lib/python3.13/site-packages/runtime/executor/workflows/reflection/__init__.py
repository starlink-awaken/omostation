# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Reflection bridge — connects autonomous_planner pipeline results to reflection infrastructure.

Functions:
    record_retrospective — Record retrospective from pipeline result
    extract_lessons      — Extract lessons from failed pipeline steps
    detect_patterns      — Detect frequent patterns from fact graph
    run_reflect          — Entry point for STEPS registry, runs full reflection cycle
"""

"""Scheduling subsystem — model selection, routing, and load balancing.

.. note::
    This subsystem is **planned but not yet wired** into production.
    The files below provide the foundation for future model scheduling:

    * ``scheduler.py`` — ModelScheduler: health check + load balance
    * ``registry.py`` — ModelRegistry: model registration and discovery
    * ``policies.py`` — Scoring policies: cost/speed/capability weights
    * ``circuit_breaker.py`` — Per-model circuit breaker
    * ``retry.py`` — Independent retry logic (duplicates ``provider._with_llm_retry``)

    When this subsystem is activated, ``detect_backends()`` and
    ``create_provider()`` will route through the scheduler for
    automatic load balancing and failover.

    Current status: **Phase 30** — architecture migration in progress.
"""

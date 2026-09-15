"""KEMS Runtime — methodology operationalization (四平面+三链+三协议)."""


class Planes:
    KNOWLEDGE = "knowledge"
    EXPERIENCE = "experience"
    METHODOLOGY = "methodology"
    SYSTEM = "system"

    MAP = {
        KNOWLEDGE: "KOS index (knowledge entities, relations, provenance)",
        EXPERIENCE: "gbrain memory (experience patterns, cases, lessons)",
        METHODOLOGY: "ontoderive (derivation rules, methodology stages)",
        SYSTEM: "ecos (health monitoring, entropy, alerts)",
    }


class Chains:
    DATA = "data"
    METHOD = "method"
    EVOLUTION = "evolution"

    MAP = {
        DATA: "kronos -> eidos -> KOS",
        METHOD: "minerva -> ontoderive -> KOS",
        EVOLUTION: "KOS self (observe -> hypothesize -> experiment -> learn)",
    }


class Protocols:
    KNOWLEDGE = "knowledge"
    PROCESS = "process"
    EVOLUTION = "evolution"

    MAP = {
        KNOWLEDGE: "eidos schema + validation rules",
        PROCESS: "pipeline:json workflow definitions",
        EVOLUTION: "KOS self adaptation rules + HITL gates",
    }


class KemsRuntime:
    def __init__(self) -> None:
        self.planes = Planes()
        self.chains = Chains()
        self.protocols = Protocols()

    def describe(self) -> dict:
        return {"planes": dict(self.planes.MAP), "chains": dict(self.chains.MAP), "protocols": dict(self.protocols.MAP)}

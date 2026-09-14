"""Shared utilities for Minerva pipeline stages.

TODO: implement full shared utilities (entity type mapping, etc.).
"""

from __future__ import annotations


def spacy_to_entity_type(spacy_label: str) -> str:
    """Map a spaCy NER label to a Minerva entity type.

    TODO: implement full spaCy label mapping.
    """
    label_map = {
        "PERSON": "person",
        "ORG": "organization",
        "GPE": "location",
        "LOC": "location",
        "DATE": "date",
        "TIME": "time",
        "MONEY": "money",
        "PERCENT": "percent",
        "PRODUCT": "product",
        "EVENT": "event",
        "WORK_OF_ART": "art",
        "LAW": "law",
        "FAC": "facility",
        "NORP": "group",
        "CARDINAL": "number",
        "ORDINAL": "number",
        "QUANTITY": "quantity",
    }
    return label_map.get(spacy_label.upper(), "unknown")


__all__ = [
    "spacy_to_entity_type",
]

"""Shared utilities used across Minerva layers."""


def spacy_to_entity_type(spacy_label: str) -> str:
    """Map spaCy NER labels to Minerva ontology entity types."""
    mapping = {
        "ORG": "Organization",
        "PERSON": "Person",
        "GPE": "Organization",
        "PRODUCT": "Product",
        "WORK_OF_ART": "Publication",
        "DATE": "Event",
        "EVENT": "Event",
    }
    return mapping.get(spacy_label, "Concept")

"""Tests for kos.ontology._types — core type definitions."""

import unittest

from kos.ontology._types import Entity, EntityType, Relation, RelationType, infer_entity_type, validate_entity_id


class TestEntityType(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(EntityType.PERSON.value, "person")
        self.assertEqual(EntityType.ORGANIZATION.value, "organization")
        self.assertEqual(EntityType.PROJECT.value, "project")
        self.assertEqual(len(EntityType), 15)

    def test_entity_dataclass(self):
        e = Entity(entity_id="ROL-test", entity_type=EntityType.PERSON, label="Test")
        self.assertEqual(e.entity_id, "ROL-test")
        self.assertEqual(e.label, "Test")
        self.assertEqual(e.aliases, [])
        self.assertEqual(e.status, "active")

    def test_entity_defaults(self):
        e = Entity(entity_id="ORG-test", entity_type=EntityType.ORGANIZATION, label="Org")
        self.assertEqual(e.version, 1)
        self.assertEqual(e.confidence, 1.0)
        self.assertEqual(e.metadata, {})


class TestRelationType(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(RelationType.REPORTS_TO.value, "reports_to")
        self.assertEqual(RelationType.MEMBER_OF.value, "member_of")
        self.assertEqual(RelationType.WORKS_ON.value, "works_on")
        self.assertEqual(len(RelationType), 10)

    def test_relation_dataclass(self):
        r = Relation(source_id="ROL-a", relation_type=RelationType.REPORTS_TO, target_id="ROL-b")
        self.assertEqual(r.source_id, "ROL-a")
        self.assertEqual(r.relation_type, RelationType.REPORTS_TO)
        self.assertEqual(r.confidence, 1.0)


class TestIdValidation(unittest.TestCase):
    def test_valid_person_id(self):
        self.assertTrue(validate_entity_id("ROL-xia-mingxing"))

    def test_valid_org_id(self):
        self.assertTrue(validate_entity_id("ORG-fsqwsj"))

    def test_valid_project_id(self):
        self.assertTrue(validate_entity_id("PRJ-digital-platform"))

    def test_invalid_id(self):
        self.assertFalse(validate_entity_id("INVALID"))
        self.assertFalse(validate_entity_id(""))
        self.assertFalse(validate_entity_id("X-s"))

    def test_infer_person(self):
        self.assertEqual(infer_entity_type("ROL-abc"), EntityType.PERSON)

    def test_infer_org(self):
        self.assertEqual(infer_entity_type("ORG-abc"), EntityType.ORGANIZATION)

    def test_infer_project(self):
        self.assertEqual(infer_entity_type("PRJ-abc"), EntityType.PROJECT)

    def test_infer_unknown(self):
        self.assertIsNone(infer_entity_type("XXX-abc"))


class TestEntityEquality(unittest.TestCase):
    def test_same_id_same_entity(self):
        e1 = Entity(entity_id="ROL-a", entity_type=EntityType.PERSON, label="A")
        e2 = Entity(entity_id="ROL-a", entity_type=EntityType.PERSON, label="A")
        self.assertEqual(e1, e2)

    def test_different_id_different_entity(self):
        e1 = Entity(entity_id="ROL-a", entity_type=EntityType.PERSON, label="A")
        e2 = Entity(entity_id="ROL-b", entity_type=EntityType.PERSON, label="B")
        self.assertNotEqual(e1, e2)


if __name__ == "__main__":
    unittest.main()

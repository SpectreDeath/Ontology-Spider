"""Core ontology model types, canonical schema vocabulary, and in-memory store."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# Canonical built-in schema relation vocabulary
INSTANCE_OF = "instance_of"
SUBCLASS_OF = "subclass_of"
DOMAIN = "domain"
RANGE = "range"
DISJOINT_WITH = "disjoint_with"
ACYCLIC = "acyclic"

BUILTIN_SCHEMA_PREDICATES = frozenset({
    INSTANCE_OF,
    SUBCLASS_OF,
    DOMAIN,
    RANGE,
    DISJOINT_WITH,
    ACYCLIC,
})


@dataclass(frozen=True)
class Entity:
    """An entity (class, instance, or property) in the ontology."""
    id: str
    name: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entity:
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            attributes=dict(data.get("attributes", {})),
        )


@dataclass(frozen=True)
class Relation:
    """A semantic triple (subject, predicate, object)."""
    subject: str
    predicate: str
    object: str

    def to_dict(self) -> dict[str, str]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Relation:
        return cls(
            subject=str(data["subject"]),
            predicate=str(data["predicate"]),
            object=str(data["object"]),
        )


@dataclass(frozen=True)
class Provenance:
    """Audit and origin metadata for an assertion."""
    source: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    turn_id: Optional[str] = None
    parent_turn_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "turn_id": self.turn_id,
            "parent_turn_ids": list(self.parent_turn_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Provenance:
        return cls(
            source=data.get("source", "unknown"),
            timestamp=data.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
            turn_id=data.get("turn_id"),
            parent_turn_ids=tuple(data.get("parent_turn_ids", [])),
        )


@dataclass(frozen=True)
class Assertion:
    """A verified triple with deterministic identity, provenance, and attributes."""
    assertion_id: str
    relation: Relation
    provenance: Provenance
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assertion_id": self.assertion_id,
            "relation": self.relation.to_dict(),
            "provenance": self.provenance.to_dict(),
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Assertion:
        return cls(
            assertion_id=data["assertion_id"],
            relation=Relation.from_dict(data["relation"]),
            provenance=Provenance.from_dict(data.get("provenance", {})),
            attributes=dict(data.get("attributes", {})),
        )


def generate_assertion_id(relation: Relation, source: str, turn_id: Optional[str] = None) -> str:
    """Generate a deterministic assertion identifier."""
    raw = f"{relation.subject}|{relation.predicate}|{relation.object}|{source}|{turn_id or ''}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"asrt_{digest}"


class OntologyModel:
    """In-memory store for entities and assertions with index-accelerated querying."""

    def __init__(self, uri: str = "urn:ontology:root") -> None:
        self.uri = uri
        self._entities: dict[str, Entity] = {}
        self._assertions: dict[str, Assertion] = {}

        # Indices
        self._by_subject: dict[str, set[str]] = {}
        self._by_predicate: dict[str, set[str]] = {}
        self._by_object: dict[str, set[str]] = {}
        self._by_turn: dict[str, set[str]] = {}

    @property
    def entities(self) -> dict[str, Entity]:
        return dict(self._entities)

    @property
    def assertions(self) -> dict[str, Assertion]:
        return dict(self._assertions)

    def add_entity(self, entity: Entity) -> None:
        """Register or update an entity."""
        self._entities[entity.id] = entity

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def add_assertion(
        self,
        relation: Relation,
        provenance: Provenance,
        assertion_id: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Assertion:
        """Add a triple assertion and update query indices."""
        # Ensure subject and object entities exist in the entity table
        if relation.subject not in self._entities:
            self.add_entity(Entity(id=relation.subject))
        if relation.object not in self._entities:
            self.add_entity(Entity(id=relation.object))

        aid = assertion_id or generate_assertion_id(
            relation, provenance.source, provenance.turn_id
        )
        asrt = Assertion(
            assertion_id=aid,
            relation=relation,
            provenance=provenance,
            attributes=dict(attributes or {}),
        )
        self._assertions[aid] = asrt

        # Indexing
        self._by_subject.setdefault(relation.subject, set()).add(aid)
        self._by_predicate.setdefault(relation.predicate, set()).add(aid)
        self._by_object.setdefault(relation.object, set()).add(aid)
        if provenance.turn_id:
            self._by_turn.setdefault(provenance.turn_id, set()).add(aid)

        return asrt

    def retract_assertion(self, assertion_id: str) -> Optional[Assertion]:
        """Retract an assertion by ID and clean indices."""
        asrt = self._assertions.pop(assertion_id, None)
        if not asrt:
            return None

        rel = asrt.relation
        if rel.subject in self._by_subject:
            self._by_subject[rel.subject].discard(assertion_id)
        if rel.predicate in self._by_predicate:
            self._by_predicate[rel.predicate].discard(assertion_id)
        if rel.object in self._by_object:
            self._by_object[rel.object].discard(assertion_id)
        if asrt.provenance.turn_id and asrt.provenance.turn_id in self._by_turn:
            self._by_turn[asrt.provenance.turn_id].discard(assertion_id)

        return asrt

    def retract_by_turn_id(self, turn_id: str) -> list[Assertion]:
        """Retract all assertions produced during a given dialog turn."""
        aids = list(self._by_turn.get(turn_id, set()))
        retracted = []
        for aid in aids:
            res = self.retract_assertion(aid)
            if res:
                retracted.append(res)
        return retracted

    def query(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
    ) -> list[Assertion]:
        """Query assertions matching the triple pattern."""
        candidates: Optional[set[str]] = None

        if subject is not None:
            candidates = set(self._by_subject.get(subject, set()))
        if predicate is not None:
            pred_set = self._by_predicate.get(predicate, set())
            candidates = pred_set if candidates is None else candidates & pred_set
        if object is not None:
            obj_set = self._by_object.get(object, set())
            candidates = obj_set if candidates is None else candidates & obj_set

        if candidates is None:
            return list(self._assertions.values())

        return [self._assertions[aid] for aid in candidates if aid in self._assertions]

    def to_dict(self) -> dict[str, Any]:
        """Serialize model to a standard dictionary."""
        return {
            "uri": self.uri,
            "entities": [e.to_dict() for e in self._entities.values()],
            "assertions": [a.to_dict() for a in self._assertions.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OntologyModel:
        """Deserialize model from a standard dictionary."""
        model = cls(uri=data.get("uri", "urn:ontology:root"))
        for edata in data.get("entities", []):
            model.add_entity(Entity.from_dict(edata))
        for adata in data.get("assertions", []):
            asrt = Assertion.from_dict(adata)
            model.add_assertion(
                relation=asrt.relation,
                provenance=asrt.provenance,
                assertion_id=asrt.assertion_id,
                attributes=asrt.attributes,
            )
        return model

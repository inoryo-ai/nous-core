"""KnowledgeStore — fact database with 4 atomic operations.

Atomic operations (proven in Level 3b / L4 / L17):
    access(concept, prop) -> value
    equal(a, b)            -> bool
    greater(a, b)          -> bool
    similar(a, b)          -> float  (0.0-1.0)

Supports numeric AND string values for business AI use cases.
"""

from collections import defaultdict
from difflib import SequenceMatcher


class KnowledgeStore:
    """Fact database indexed by (concept, property) pairs."""

    def __init__(self):
        self.facts = {}
        self.confidence = {}
        self.categories = defaultdict(list)
        self.rules = {}

        self._props_by_concept = defaultdict(set)
        self._concepts_by_prop = defaultdict(set)

        self.learn_count = 0

    def store_fact(self, concept, prop, value, conf=1.0):
        """Store a fact. If contradicting an existing higher-confidence fact, returns 'contradiction'."""
        key = (concept, prop)
        if key in self.facts:
            old_conf = self.confidence[key]
            if self.facts[key] != value and conf >= 0.5 and old_conf >= 0.5:
                return "contradiction"
            if conf > old_conf:
                self.facts[key] = value
                self.confidence[key] = conf
        else:
            self.facts[key] = value
            self.confidence[key] = conf
            self._props_by_concept[concept].add(prop)
            self._concepts_by_prop[prop].add(concept)
        self.learn_count += 1
        return "stored"

    def store_category(self, concept, category):
        if category not in self.categories[concept]:
            self.categories[concept].append(category)

    def store_rule(self, condition, result, conf=1.0):
        self.rules[condition] = (result, conf)

    def access(self, concept, prop):
        """Atomic: retrieve value, or None if missing."""
        return self.facts.get((concept, prop))

    @staticmethod
    def equal(a, b):
        """Atomic: exact equality."""
        return a == b

    @staticmethod
    def greater(a, b):
        """Atomic: ordered comparison. Returns None if either is None."""
        if a is None or b is None:
            return None
        try:
            return a > b
        except TypeError:
            return None

    @staticmethod
    def similar(a, b):
        """Atomic: similarity 0.0-1.0 between two values.

        Numeric: inverse-distance normalized.
        String: sequence ratio.
        Mixed: 0.0.
        """
        if a is None or b is None:
            return 0.0
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if a == b:
                return 1.0
            scale = max(abs(a), abs(b), 1.0)
            return max(0.0, 1.0 - abs(a - b) / scale)
        if isinstance(a, str) and isinstance(b, str):
            return SequenceMatcher(None, a, b).ratio()
        return 0.0

    def lookup(self, concept, prop):
        """Return (value, confidence) or (None, 0.0)."""
        key = (concept, prop)
        if key in self.facts:
            return self.facts[key], self.confidence[key]
        return None, 0.0

    def lookup_value(self, concept, prop):
        """Shorthand for .access()."""
        return self.facts.get((concept, prop))

    def find_all_with_property(self, prop):
        """[(concept, value, confidence)] for all concepts having `prop`."""
        results = []
        for c in self._concepts_by_prop.get(prop, ()):
            key = (c, prop)
            results.append((c, self.facts[key], self.confidence[key]))
        return results

    def find_properties(self, concept):
        """{prop: value} for all properties of `concept`."""
        return {
            p: self.facts[(concept, p)]
            for p in self._props_by_concept.get(concept, ())
        }

    def get_categories(self, concept):
        return self.categories.get(concept, [])

    def find_rule(self, condition):
        return self.rules.get(condition, (None, 0.0))

    def get_all_concepts(self):
        return list(self._props_by_concept.keys())

    def get_all_properties(self):
        return list(self._concepts_by_prop.keys())

    def fact_count(self):
        return len(self.facts)

    def concept_count(self):
        return len(self._props_by_concept)

    def summary(self):
        return (f"Facts: {self.fact_count()}, Concepts: {self.concept_count()}, "
                f"Properties: {len(self._concepts_by_prop)}, Rules: {len(self.rules)}")

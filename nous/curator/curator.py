"""Curator — bridges BookShelf and KnowledgeStore.

Three roles:
  1. CHECKOUT: Select relevant books for a query, load entries into KS
  2. RETRIEVE: Find best-matching knowledge for a query
  3. RETURN:   Clear KS entries that were borrowed from books

Design: Curator is stateless about data. All data lives in BookShelf.
KS is a temporary workspace; between goals it should be cleared.
"""


class Curator:
    """Librarian between BookShelf (books) and KnowledgeStore (desk)."""

    def __init__(self, shelf, ks):
        self.shelf = shelf
        self.ks = ks
        self._checked_out = {}  # book_name -> [concept_keys]

    def checkout(self, book_name, keys=None):
        """Load book entries into KS. If keys=None, load all.

        Returns the list of concepts that were checked out into KS.
        """
        book = self.shelf.get(book_name)
        if book is None:
            return []

        target_keys = keys if keys is not None else book.keys()
        added = []
        for k in target_keys:
            entry = book.get(k)
            if entry is None:
                continue
            concept = f"{book_name}::{k}"
            self._store_entry_into_ks(concept, entry)
            added.append(concept)

        self._checked_out.setdefault(book_name, []).extend(added)
        return added

    def _store_entry_into_ks(self, concept, entry):
        """Flatten an entry (dict/list/scalar) into (concept, prop) -> value facts."""
        if isinstance(entry, dict):
            for prop, val in entry.items():
                self.ks.store_fact(concept, prop, val)
        elif isinstance(entry, list):
            for i, v in enumerate(entry):
                self.ks.store_fact(concept, f"item_{i}", v)
        else:
            self.ks.store_fact(concept, "value", entry)

    def retrieve(self, query, limit=5, books=None):
        """Fetch relevant entries across books for a natural-language query.

        Does NOT store into KS. Used for lookup-style queries.

        Returns: [{"book": str, "key": str, "entry": value, "score": float}]
        """
        raw = self.shelf.search(query, limit=limit, books=books)
        return [
            {"book": bname, "key": k, "entry": v, "score": round(s, 4)}
            for bname, k, v, s in raw
        ]

    def best_match(self, query, books=None, min_score=0.2):
        """Return the single best matching entry, or None if nothing passes."""
        results = self.retrieve(query, limit=1, books=books)
        if not results:
            return None
        top = results[0]
        if top["score"] < min_score:
            return None
        return top

    def return_all(self):
        """Clear all checked-out concepts from KS. Keeps patterns/rules."""
        count = 0
        for book_name, concepts in self._checked_out.items():
            for c in concepts:
                props = list(self.ks._props_by_concept.get(c, ()))
                for p in props:
                    self.ks.facts.pop((c, p), None)
                    self.ks.confidence.pop((c, p), None)
                    self.ks._concepts_by_prop[p].discard(c)
                self.ks._props_by_concept.pop(c, None)
                count += 1
        self._checked_out.clear()
        return count

    def checked_out_summary(self):
        return {bn: len(cs) for bn, cs in self._checked_out.items()}

"""BookShelf — persistent knowledge store on disk.

A Book is an immutable JSON knowledge DB. BookShelf is a registry with
text-search across all registered books. Used by Curator to fetch
relevant knowledge into KS on demand.

Separation of concerns:
  - Books = long-term memory (JSON files, never forgotten)
  - KS    = working memory (loaded on demand, cleared between goals)
"""

import json


class Book:
    """Read-only JSON knowledge DB with lazy loading."""

    def __init__(self, name, path, schema=None):
        self.name = name
        self.path = path
        self.schema = schema or {}
        self._data = None
        self._meta = None

    def _load(self):
        if self._data is not None:
            return
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict) and "_meta" in raw:
            self._meta = raw.pop("_meta")
            self._data = raw
        else:
            self._data = raw
            self._meta = {}

    @property
    def data(self):
        self._load()
        return self._data

    @property
    def meta(self):
        self._load()
        return self._meta

    def keys(self):
        return list(self.data.keys())

    def get(self, key):
        return self.data.get(str(key))

    def query(self, condition, limit=10):
        """Return [(key, value)] where condition(key, value) is True."""
        results = []
        for k, v in self.data.items():
            if k == "_meta":
                continue
            if condition(k, v):
                results.append((k, v))
                if len(results) >= limit:
                    break
        return results

    def search_text(self, query, limit=5):
        """Fuzzy text search across entries.

        Scoring layers (max of):
          - key appears in query      -> 0.60 + 0.30 * coverage
          - query appears in blob     -> 0.85
          - char-2gram overlap (blob) -> up to 1.0
          - char-2gram overlap (key)  -> up to 0.80

        Works across JP/EN without external NLP. Returns [(key, entry, score)].
        """
        scores = []
        q = query.lower()
        for k, v in self.data.items():
            if k == "_meta":
                continue
            key_str = str(k).lower()
            blob = self._entry_text(k, v).lower()

            score = 0.0
            if key_str and key_str in q:
                coverage = min(len(key_str) / max(len(q), 1), 1.0)
                score = max(score, 0.60 + 0.30 * coverage)
            if q in blob:
                score = max(score, 0.85)
            score = max(score, self._ngram_overlap(q, blob))
            if key_str:
                score = max(score, self._ngram_overlap(q, key_str) * 0.80)

            if score > 0:
                scores.append((k, v, score))
        scores.sort(key=lambda x: x[2], reverse=True)
        return scores[:limit]

    @staticmethod
    def _ngram_overlap(q, b, n=2):
        """Fraction of q's char-n-grams that appear in b."""
        if len(q) < n:
            return 1.0 if q in b else 0.0
        grams = set()
        for i in range(len(q) - n + 1):
            g = q[i:i + n]
            if g.strip():
                grams.add(g)
        if not grams:
            return 0.0
        hits = sum(1 for g in grams if g in b)
        return hits / len(grams)

    @staticmethod
    def _entry_text(key, value):
        parts = [str(key)]
        if isinstance(value, dict):
            for vv in value.values():
                parts.append(str(vv))
        elif isinstance(value, list):
            parts.extend(str(x) for x in value)
        else:
            parts.append(str(value))
        return " ".join(parts)

    def __len__(self):
        return sum(1 for k in self.data.keys() if k != "_meta")


class WritableBook(Book):
    """Book that NOUS can write back to."""

    def add_entry(self, key, value):
        self._load()
        self._data[str(key)] = value

    def update_entry(self, key, value):
        self._load()
        self._data[str(key)] = value

    def delete_entry(self, key):
        self._load()
        self._data.pop(str(key), None)

    def save(self):
        """Persist to disk."""
        self._load()
        out = dict(self._data)
        if self._meta:
            out["_meta"] = self._meta
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)


class BookShelf:
    """Registry of books + cross-book text search."""

    def __init__(self):
        self._books = {}

    def register(self, book):
        self._books[book.name] = book
        return book

    def load_book(self, name, path, schema=None, writable=False):
        cls = WritableBook if writable else Book
        book = cls(name, path, schema)
        return self.register(book)

    def get(self, name):
        return self._books.get(name)

    def names(self):
        return list(self._books.keys())

    def __contains__(self, name):
        return name in self._books

    def __len__(self):
        return len(self._books)

    def search(self, query, limit=5, books=None):
        """Cross-book text search.

        Args:
            query: search string
            limit: max results across all books
            books: list of book names to search (default: all)

        Returns: [(book_name, key, value, score)] sorted by score desc.
        """
        target_books = books or self.names()
        results = []
        for bname in target_books:
            book = self._books.get(bname)
            if not book:
                continue
            for k, v, s in book.search_text(query, limit=limit):
                results.append((bname, k, v, s))
        results.sort(key=lambda x: x[3], reverse=True)
        return results[:limit]

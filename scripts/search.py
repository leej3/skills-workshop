"""Small, explainable lexical ranking; indexes are rebuilt from authoritative text."""

from __future__ import annotations

import math
import re
from collections import Counter
from difflib import get_close_matches
from typing import Any

WORD = re.compile(r"[^\W_]+", re.UNICODE)
STOP = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "please",
    "previously",
    "something",
    "that",
    "the",
    "their",
    "them",
    "there",
    "these",
    "they",
    "this",
    "to",
    "used",
    "using",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
    "would",
    "you",
    "your",
    "skill",
    "skills",
}


def tokens(text: str) -> list[str]:
    return [word for word in WORD.findall(text.casefold()) if word not in STOP]


def rank(
    query: str, documents: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    """Rank weighted fields with IDF, saturated frequency, coverage and typo fallback.

    Each document contains a public result and fields of (weight, text). Never
    interpret skill contents as executable instructions. No remote embeddings.
    """
    terms = list(dict.fromkeys(tokens(query)))
    if not terms and query.strip():
        return []
    indexed = []
    frequency: Counter[str] = Counter()
    for document in documents:
        fields = [
            (name, weight, Counter(tokens(text)))
            for name, (weight, text) in document["fields"].items()
        ]
        vocabulary = set().union(*(set(counts) for _, _, counts in fields))
        frequency.update(vocabulary)
        indexed.append((document, fields))
    vocabulary = sorted(frequency)
    expansions = {}
    for term in terms:
        if term in frequency:
            expansions[term] = [(term, 1.0)]
        else:
            prefixes = [
                word for word in vocabulary if len(term) >= 4 and word.startswith(term)
            ]
            matches = prefixes[:12] or (
                get_close_matches(term, vocabulary, n=2, cutoff=0.82)
                if len(term) >= 5
                else []
            )
            expansions[term] = [(word, 0.7) for word in matches]
    results = []
    for document, fields in indexed:
        score = 0.0
        matched = []
        matched_fields = set()
        for term in terms:
            best = 0.0
            for word, quality in expansions[term]:
                idf = math.log(1 + (len(documents) + 1) / (frequency[word] + 1))
                value = 0.0
                for name, weight, counts in fields:
                    count = counts[word]
                    if count:
                        value += weight * (count / (count + 1)) * idf * quality
                        matched_fields.add(name)
                best = max(best, value)
            if best:
                matched.append(term)
                score += best
        if terms and not matched:
            continue
        coverage = len(matched) / len(terms) if terms else 1
        score *= coverage * coverage
        result = dict(document["result"])
        result.update(
            score=round(score, 4),
            matched_terms=matched,
            matched_fields=sorted(matched_fields),
        )
        results.append(result)
    return sorted(
        results, key=lambda row: (-row["score"], row["name"], row.get("path", ""))
    )[:limit]

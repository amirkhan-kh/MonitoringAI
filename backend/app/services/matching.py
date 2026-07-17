from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from threading import Lock

from sqlalchemy.orm import Session

from app.models import Brand


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.casefold()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


@dataclass(frozen=True)
class BrandMatch:
    brand: Brand | None
    terms: list[str]


@dataclass(frozen=True)
class _BrandTerms:
    brand_id: uuid.UUID
    terms: tuple[str, ...]
    ignore_terms: tuple[str, ...]


# Ingestion matches every incoming message against every active brand. Reloading
# the full brands table per message is wasteful, so cache a lightweight snapshot
# (normalized terms only) per process with a short TTL. The matched brand object
# itself is fetched once via the session identity map, not the whole table.
_BRAND_CACHE_TTL_SECONDS = 60.0
_brand_terms_cache: list[_BrandTerms] = []
_brand_cache_expiry = 0.0
_brand_cache_lock = Lock()


def _load_brand_terms(session: Session) -> list[_BrandTerms]:
    brands = session.query(Brand).filter(Brand.active.is_(True)).all()
    entries: list[_BrandTerms] = []
    for brand in brands:
        entries.append(
            _BrandTerms(
                brand_id=brand.id,
                terms=tuple(collect_terms(brand_match_candidates(brand))),
                ignore_terms=tuple(collect_terms(brand.ignore_terms)),
            )
        )
    return entries


def _get_brand_terms(session: Session) -> list[_BrandTerms]:
    global _brand_terms_cache, _brand_cache_expiry
    now = time.monotonic()
    if now < _brand_cache_expiry and _brand_terms_cache is not None:
        return _brand_terms_cache
    with _brand_cache_lock:
        if time.monotonic() < _brand_cache_expiry and _brand_terms_cache:
            return _brand_terms_cache
        _brand_terms_cache = _load_brand_terms(session)
        _brand_cache_expiry = time.monotonic() + _BRAND_CACHE_TTL_SECONDS
        return _brand_terms_cache


def invalidate_brand_cache() -> None:
    """Force the next match to reload brands (call after brand create/update)."""
    global _brand_cache_expiry
    _brand_cache_expiry = 0.0


def match_brand(session: Session, text: str, preferred_brand: Brand | None = None) -> BrandMatch:
    normalized = normalize_text(text)
    if not normalized:
        return BrandMatch(preferred_brand, [])

    if preferred_brand:
        terms = collect_matched_terms(preferred_brand, normalized)
        return BrandMatch(preferred_brand, terms)

    best_id: uuid.UUID | None = None
    best_terms: list[str] = []
    for entry in _get_brand_terms(session):
        if any(term_matches(normalized, term) for term in entry.ignore_terms):
            continue
        terms = [term for term in entry.terms if term_matches(normalized, term)]
        if len(terms) > len(best_terms):
            best_id = entry.brand_id
            best_terms = terms

    if best_id is None:
        return BrandMatch(None, [])
    brand = session.get(Brand, best_id)
    return BrandMatch(brand, best_terms if brand else [])


def collect_matched_terms(brand: Brand, normalized_text: str) -> list[str]:
    candidates = collect_terms(brand_match_candidates(brand))
    return [term for term in candidates if term_matches(normalized_text, term)]


def collect_ignored_terms(brand: Brand, normalized_text: str) -> list[str]:
    return [term for term in collect_terms(brand.ignore_terms) if term_matches(normalized_text, term)]


def term_matches(normalized_text: str, normalized_term: str) -> bool:
    if not normalized_text or not normalized_term:
        return False
    if normalized_term.startswith(("#", "@")):
        return re.search(rf"{re.escape(normalized_term)}(?![\w])", normalized_text) is not None
    return re.search(rf"(?<![\w]){re.escape(normalized_term)}(?![\w])", normalized_text) is not None


def brand_match_candidates(brand: Brand) -> list[str]:
    return [
        brand.name,
        brand.industry,
        brand.primary_category,
        *(brand.category_path or []),
        *(brand.aliases or []),
        *(brand.keywords or []),
        *(brand.products or []),
        *(brand.competitors or []),
        *(brand.risk_keywords or []),
        *(brand.positive_keywords or []),
    ]


def collect_terms(values: list[str] | None) -> list[str]:
    terms: list[str] = []
    for value in values or []:
        normalized = normalize_text(value)
        if normalized and normalized not in terms:
            terms.append(normalized)
    return terms

"""Filtering: keep only US roles matching the configured category/role targets.

A job passes only if it is (1) a configured role type for its category,
(2) in an allowed season/year when applicable, and (3) US-located. As a side
effect, `apply_filters` annotates each kept Job with `.category`, `.season`,
`.year`.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable, Optional

from . import config
from .models import Job

_YEAR_RE = re.compile(r"\b(20\d{2})\b")

# Map detection keywords -> canonical season label.
_SEASON_KEYWORDS = [
    ("summer", "summer"),
    ("spring", "spring"),
    ("autumn", "fall"),
    ("fall", "fall"),
    ("winter", "winter"),
    ("off-cycle", "offcycle"),
    ("off cycle", "offcycle"),
    ("offcycle", "offcycle"),
]

_FULLTIME_VARIANTS = {"full-time", "full time", "fulltime"}


def _lc(s: str) -> str:
    return (s or "").lower()


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


@lru_cache(maxsize=8)
def _loc_regex(terms: tuple[str, ...]):
    """Compile location terms into one alternation that won't match inside a
    longer word — so ", ca" matches "Austin, TX | ..., CA" but NOT ", canada",
    and "china" doesn't match "chinatown"."""
    if not terms:
        return None
    pattern = "(?:" + "|".join(re.escape(t) for t in terms) + ")(?![a-z])"
    return re.compile(pattern)


def _loc_match(text: str, terms: Iterable[str]) -> bool:
    rx = _loc_regex(tuple(terms))
    return bool(rx.search(text)) if rx else False


def detect_season(job: Job) -> Optional[str]:
    if job.season:
        s = job.season.lower()
        for kw, canon in _SEASON_KEYWORDS:
            if kw in s:
                return canon
        return s  # already a canonical-ish value from the source
    title = _lc(job.title)
    for kw, canon in _SEASON_KEYWORDS:
        if kw in title:
            return canon
    return None


def detect_year(job: Job) -> Optional[int]:
    if job.year:
        return job.year
    m = _YEAR_RE.search(job.title or "")
    return int(m.group(1)) if m else None


def is_internship(title_lc: str, role_cfg: dict) -> bool:
    intern_terms = [t.lower() for t in role_cfg.get("internship_terms", [])]
    if not _contains_any(title_lc, intern_terms):
        return False
    # Hard seniority excludes never co-occur with a genuine internship.
    hard_excludes = [
        e.lower()
        for e in role_cfg.get("exclude_terms", [])
        if e.lower() not in _FULLTIME_VARIANTS
    ]
    if _contains_any(title_lc, hard_excludes):
        return False
    return True


def is_new_grad(title_lc: str, role_cfg: dict) -> bool:
    intern_terms = [t.lower() for t in role_cfg.get("internship_terms", [])]
    if _contains_any(title_lc, intern_terms):
        return False
    hard_excludes = [
        e.lower()
        for e in role_cfg.get("exclude_terms", [])
        if e.lower() not in _FULLTIME_VARIANTS
    ]
    if _contains_any(title_lc, hard_excludes):
        return False
    new_grad_terms = [t.lower() for t in role_cfg.get("new_grad_terms", [])]
    return _contains_any(title_lc, new_grad_terms)


def classify_category(title_lc: str, categories_cfg: dict) -> Optional[str]:
    # Dict order is significant (quant before swe before consulting).
    for cat, terms in categories_cfg.items():
        if _contains_any(title_lc, [t.lower() for t in terms]):
            return cat
    return None


def role_target_for_category(category: str, role_cfg: dict) -> str:
    targets = role_cfg.get("targets_by_category")
    if not targets:
        return "internship" if role_cfg.get("require_internship", True) else "any"
    return str(targets.get(category, targets.get("default", "any"))).lower()


def is_us_location(job: Job, loc_cfg: dict) -> bool:
    if not loc_cfg.get("require_us", True):
        return True
    text = _lc(job.location_str)
    if not text.strip():
        return bool(loc_cfg.get("keep_when_location_unknown", True))
    us_terms = [t.lower() for t in loc_cfg.get("us_terms", [])]
    non_us_terms = [t.lower() for t in loc_cfg.get("non_us_terms", [])]
    has_us = _loc_match(text, us_terms)
    has_non_us = _loc_match(text, non_us_terms)
    if has_us:
        return True  # a US option exists (handles multi-location postings)
    if has_non_us:
        return False
    return bool(loc_cfg.get("keep_when_location_unknown", True))


def passes(job: Job, f: dict) -> bool:
    """Return True if the job should be kept; annotates the job in place."""
    title_lc = _lc(job.title)
    role_cfg = f.get("role", {})
    loc_cfg = f.get("location", {})

    # 1) Category.
    category = classify_category(title_lc, f.get("categories", {}))
    if f.get("require_category", True) and not category:
        return False
    job.category = category or "other"

    # 2) Category-specific role target.
    target = role_target_for_category(job.category, role_cfg)
    if target == "internship" and not is_internship(title_lc, role_cfg):
        return False
    if target in {"new_grad", "new-grad", "newgrad"} and not is_new_grad(title_lc, role_cfg):
        return False
    if target not in {"internship", "new_grad", "new-grad", "newgrad", "any"}:
        return False

    # 3) Season window.
    season = detect_season(job)
    allowed_seasons = [s.lower() for s in role_cfg.get("seasons", [])]
    if allowed_seasons and season and season not in allowed_seasons:
        return False
    job.season = season

    # 4) Year window.
    year = detect_year(job)
    allowed_years = role_cfg.get("years", [])
    if allowed_years and year and year not in allowed_years:
        return False
    job.year = year

    # 5) US location.
    if not is_us_location(job, loc_cfg):
        return False

    return True


def apply_filters(jobs: list[Job], f: Optional[dict] = None) -> list[Job]:
    f = f if f is not None else config.filters()
    return [j for j in jobs if passes(j, f)]

"""Discord digest via incoming webhook."""

from __future__ import annotations

import logging

import requests

from ..models import Job
from .email import _CATEGORY_LABELS, faang_jobs, group_by_category

log = logging.getLogger(__name__)

DISCORD_EMBED_DESCRIPTION_LIMIT = 3500
DISCORD_MESSAGE_EMBED_CHAR_LIMIT = 5800


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "..."


def _job_line(job: Job) -> str:
    loc = job.location_str or "Location not listed"
    meta_bits = [loc, job.season, str(job.year) if job.year else None]
    meta = " - ".join(bit for bit in meta_bits if bit)
    return _truncate(f"[{job.title}]({job.url})\n{job.company} - {meta}", 700)


def build_content(
    jobs: list[Job],
    grouped: list[tuple[str, list[Job]]],
    prefix: str,
    faang: list[Job],
) -> str:
    if faang:
        names = ", ".join(sorted({j.company for j in faang}))
        return _truncate(f"FAANG job out now: {names} ({len(jobs)} new role(s))", 2000)
    summary = ", ".join(
        f"{len(group)} {_CATEGORY_LABELS.get(cat, cat).split(' ', 1)[-1]}"
        for cat, group in grouped
    )
    return _truncate(f"{prefix} {len(jobs)} new role(s): {summary}", 2000)


DISCORD_MAX_EMBEDS = 10


def _embed_size(embed: dict) -> int:
    return len(embed.get("title", "")) + len(embed.get("description", ""))


def _job_pages(jobs: list[Job], max_jobs: int):
    page: list[Job] = []
    page_len = 0
    for job in jobs:
        line_len = len(_job_line(job))
        separator_len = 2 if page else 0
        if page and (
            len(page) >= max_jobs
            or page_len + separator_len + line_len > DISCORD_EMBED_DESCRIPTION_LIMIT
        ):
            yield page
            page = []
            page_len = 0
            separator_len = 0
        page.append(job)
        page_len += separator_len + line_len
    if page:
        yield page


def build_embeds(jobs: list[Job], discord_cfg: dict) -> list[dict]:
    order = discord_cfg.get("category_order", ["quant", "swe", "other"])
    grouped = group_by_category(jobs, order)
    jobs_per_embed = max(
        1,
        int(discord_cfg.get("jobs_per_embed", discord_cfg.get("max_jobs_per_category", 10))),
    )
    embeds = []
    for cat, group in grouped:
        sorted_jobs = sorted(group, key=lambda x: (x.company.lower(), x.title.lower()))
        label = _CATEGORY_LABELS.get(cat, cat)
        pages = list(_job_pages(sorted_jobs, jobs_per_embed))
        start_index = 1
        for page in pages:
            end_index = start_index + len(page) - 1
            title = f"{label} ({len(sorted_jobs)})"
            if len(pages) > 1:
                title = f"{label} ({start_index}-{end_index} of {len(sorted_jobs)})"
            description = "\n\n".join(_job_line(j) for j in page)
            embeds.append(
                {
                    "title": title,
                    "description": _truncate(description, DISCORD_EMBED_DESCRIPTION_LIMIT),
                    "color": 0x5865F2,
                }
            )
            start_index = end_index + 1
    return embeds


def _embed_batches(embeds: list[dict]):
    batch: list[dict] = []
    batch_chars = 0
    for embed in embeds:
        embed_chars = _embed_size(embed)
        if batch and (
            len(batch) >= DISCORD_MAX_EMBEDS
            or batch_chars + embed_chars > DISCORD_MESSAGE_EMBED_CHAR_LIMIT
        ):
            yield batch
            batch = []
            batch_chars = 0
        batch.append(embed)
        batch_chars += embed_chars
    if batch:
        yield batch


def send_discord(jobs: list[Job], secrets: dict[str, str], discord_cfg: dict) -> bool:
    """Send the digest. Returns True if sent, False if skipped/failed."""
    webhook_url = secrets.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        log.warning("discord skipped: DISCORD_WEBHOOK_URL not set")
        return False

    order = discord_cfg.get("category_order", ["quant", "swe", "other"])
    grouped = group_by_category(jobs, order)
    faang = faang_jobs(jobs, discord_cfg.get("faang_companies", []))
    content = build_content(
        jobs,
        grouped,
        discord_cfg.get("subject_prefix", "[Job Alert]"),
        faang,
    )
    embeds = build_embeds(jobs, discord_cfg)

    try:
        sent_batches = 0
        for batch in _embed_batches(embeds):
            payload = {"embeds": batch}
            if sent_batches == 0:
                payload["content"] = content
            response = requests.post(webhook_url, json=payload, timeout=15)
            response.raise_for_status()
            sent_batches += 1
        log.info(
            "discord webhook sent (%d jobs across %d message(s))",
            len(jobs),
            sent_batches,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("discord webhook failed: %s", exc)
        return False

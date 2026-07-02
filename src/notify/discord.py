"""Discord digest via incoming webhook."""

from __future__ import annotations

import json
import logging


import requests

from ..models import Job
from .email import _CATEGORY_LABELS, faang_jobs, group_by_category

log = logging.getLogger(__name__)

DISCORD_EMBED_LIMIT = 6000
ATTACHMENT_NOTE = "Open the attached jobs.txt for the full list."


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "..."


def _job_line(job: Job) -> str:
    loc = job.location_str or "Location not listed"
    meta_bits = [loc, job.season, str(job.year) if job.year else None]
    meta = " - ".join(bit for bit in meta_bits if bit)
    return _truncate(f"[{job.title}]({job.url})\n{job.company} - {meta}", 1000)


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


def has_overflow(jobs: list[Job], discord_cfg: dict) -> bool:
    order = discord_cfg.get("category_order", ["quant", "swe", "other"])
    grouped = group_by_category(jobs, order)
    max_jobs = int(discord_cfg.get("max_jobs_per_category", 10))
    return any(len(group) > max_jobs for _, group in grouped)


def build_attachment_text(jobs: list[Job], discord_cfg: dict) -> str:
    order = discord_cfg.get("category_order", ["quant", "swe", "other"])
    grouped = group_by_category(jobs, order)
    lines = [f"{len(jobs)} new matching role(s)", ""]
    for cat, group in grouped:
        label = _CATEGORY_LABELS.get(cat, cat)
        lines.append(f"== {label} ({len(group)}) ==")
        for job in sorted(group, key=lambda x: (x.company.lower(), x.title.lower())):
            loc = job.location_str or "Location not listed"
            lines.append(f"- {job.title} -- {job.company} [{loc}]")
            lines.append(f"  {job.url}")
        lines.append("")
    return "\n".join(lines)


def build_embeds(jobs: list[Job], discord_cfg: dict) -> list[dict]:
    order = discord_cfg.get("category_order", ["quant", "swe", "other"])
    grouped = group_by_category(jobs, order)
    max_jobs = int(discord_cfg.get("max_jobs_per_category", 10))
    embeds = []
    for cat, group in grouped:
        sorted_jobs = sorted(group, key=lambda x: (x.company.lower(), x.title.lower()))
        shown = sorted_jobs[:max_jobs]
        description = "\n\n".join(_job_line(j) for j in shown)
        if len(sorted_jobs) > len(shown):
            description += f"\n\n...and {len(sorted_jobs) - len(shown)} more. {ATTACHMENT_NOTE}"
        embeds.append(
            {
                "title": f"{_CATEGORY_LABELS.get(cat, cat)} ({len(sorted_jobs)})",
                "description": _truncate(description, DISCORD_EMBED_LIMIT - 256),
                "color": 0x5865F2,
            }
        )
    return embeds


def send_discord(jobs: list[Job], secrets: dict[str, str], discord_cfg: dict) -> bool:
    """Send the digest. Returns True if sent, False if skipped/failed."""
    webhook_url = secrets.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        log.warning("discord skipped: DISCORD_WEBHOOK_URL not set")
        return False

    order = discord_cfg.get("category_order", ["quant", "swe", "other"])
    grouped = group_by_category(jobs, order)
    faang = faang_jobs(jobs, discord_cfg.get("faang_companies", []))
    payload = {
        "content": build_content(
            jobs,
            grouped,
            discord_cfg.get("subject_prefix", "[Job Alert]"),
            faang,
        ),
        "embeds": build_embeds(jobs, discord_cfg),
    }

    try:
        if has_overflow(jobs, discord_cfg):
            response = requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload)},
                files={
                    "files[0]": (
                        "jobs.txt",
                        build_attachment_text(jobs, discord_cfg),
                        "text/plain",
                    )
                },
                timeout=15,
            )
        else:
            response = requests.post(webhook_url, json=payload, timeout=15)
        response.raise_for_status()
        log.info("discord webhook sent (%d jobs)", len(jobs))
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("discord webhook failed: %s", exc)
        return False

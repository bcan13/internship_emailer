"""Discord webhook digest behaviour."""

from src.models import Job
from src.notify import discord as D


def _job(company, title="Software Engineer, New Grad", category="swe", url=None):
    return Job(
        company=company,
        title=title,
        url=url or f"https://x/{company}",
        locations=["New York, NY"],
        category=category,
    )


def test_build_content_summarizes_roles():
    jobs = [_job("Acme"), _job("Jane Street", "Quantitative Trading Intern", "quant")]
    grouped = [("quant", [jobs[1]]), ("swe", [jobs[0]])]
    content = D.build_content(jobs, grouped, "[Job Alert]", [])
    assert content.startswith("[Job Alert] 2 new role(s)")
    assert "Quant / Trading" in content


def test_build_embeds_group_by_category():
    jobs = [_job("Acme"), _job("Jane Street", "Quantitative Trading Intern", "quant")]
    embeds = D.build_embeds(jobs, {"category_order": ["quant", "swe"]})
    assert embeds[0]["title"].startswith("📈 Quant / Trading")
    assert "Jane Street" in embeds[0]["description"]
    assert embeds[1]["title"].startswith("💻 Software Engineering")


def test_send_discord_posts_webhook(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(D.requests, "post", fake_post)
    assert D.send_discord([_job("Acme")], {"DISCORD_WEBHOOK_URL": "https://discord.test/hook"}, {})
    assert calls[0][0] == "https://discord.test/hook"
    assert calls[0][1]["json"]["embeds"]



def test_build_embeds_paginates_full_list_when_truncated():
    jobs = [_job(f"Acme{i}") for i in range(3)]
    embeds = D.build_embeds(jobs, {"category_order": ["swe"], "jobs_per_embed": 1})
    assert len(embeds) == 3
    assert embeds[0]["title"].endswith("(1-1 of 3)")
    assert embeds[1]["title"].endswith("(2-2 of 3)")
    assert "Acme0" in embeds[0]["description"]
    assert "Acme1" in embeds[1]["description"]
    assert "Acme2" in embeds[2]["description"]
    assert "...and" not in embeds[0]["description"]


def test_send_discord_splits_more_than_ten_embeds(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(D.requests, "post", fake_post)
    jobs = [_job(f"Acme{i}") for i in range(11)]
    assert D.send_discord(
        jobs,
        {"DISCORD_WEBHOOK_URL": "https://discord.test/hook"},
        {"category_order": ["swe"], "jobs_per_embed": 1},
    )
    assert len(calls) == 2
    assert len(calls[0][1]["json"]["embeds"]) == 10
    assert len(calls[1][1]["json"]["embeds"]) == 1
    assert "content" in calls[0][1]["json"]
    assert "content" not in calls[1][1]["json"]


def test_build_embeds_respects_description_limit():
    long_url = "https://example.com/" + "a" * 900
    jobs = [_job(f"Acme{i}", url=f"{long_url}{i}") for i in range(12)]
    embeds = D.build_embeds(jobs, {"category_order": ["swe"], "jobs_per_embed": 12})
    assert len(embeds) > 1
    assert all(len(embed["description"]) <= D.DISCORD_EMBED_DESCRIPTION_LIMIT for embed in embeds)


def test_embed_batches_respect_total_message_char_limit():
    embeds = [
        {"title": f"Page {i}", "description": "x" * 2000}
        for i in range(4)
    ]
    batches = list(D._embed_batches(embeds))
    assert len(batches) == 2
    assert all(
        sum(D._embed_size(embed) for embed in batch) <= D.DISCORD_MESSAGE_EMBED_CHAR_LIMIT
        for batch in batches
    )

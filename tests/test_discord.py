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



def test_build_embeds_mentions_attachment_when_truncated():
    jobs = [_job(f"Acme{i}") for i in range(3)]
    embeds = D.build_embeds(jobs, {"category_order": ["swe"], "max_jobs_per_category": 1})
    assert "...and 2 more" in embeds[0]["description"]
    assert "jobs.txt" in embeds[0]["description"]


def test_build_attachment_text_includes_all_jobs():
    jobs = [_job(f"Acme{i}") for i in range(3)]
    text = D.build_attachment_text(jobs, {"category_order": ["swe"]})
    assert "Acme0" in text
    assert "Acme1" in text
    assert "Acme2" in text


def test_send_discord_attaches_full_list_when_truncated(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(D.requests, "post", fake_post)
    jobs = [_job(f"Acme{i}") for i in range(3)]
    assert D.send_discord(
        jobs,
        {"DISCORD_WEBHOOK_URL": "https://discord.test/hook"},
        {"category_order": ["swe"], "max_jobs_per_category": 1},
    )
    assert "files" in calls[0][1]
    assert calls[0][1]["files"]["files[0]"][0] == "jobs.txt"

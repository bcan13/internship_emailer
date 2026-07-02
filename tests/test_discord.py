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

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return Response()

    monkeypatch.setattr(D.requests, "post", fake_post)
    assert D.send_discord([_job("Acme")], {"DISCORD_WEBHOOK_URL": "https://discord.test/hook"}, {})
    assert calls[0][0] == "https://discord.test/hook"
    assert calls[0][1]["embeds"]

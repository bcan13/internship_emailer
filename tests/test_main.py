from src import main
from src.models import Job


def _job():
    return Job(company="Acme", title="Software Engineer, New Grad", url="https://example.com/job")


def _patch_run(monkeypatch, tmp_path, send_result):
    state_path = tmp_path / "seen_jobs.json"
    monkeypatch.setattr(main, "collect_jobs", lambda limit=None: [_job()])
    monkeypatch.setattr(main, "apply_filters", lambda jobs: jobs)
    monkeypatch.setattr(main.config, "state_path", lambda: state_path)
    monkeypatch.setattr(main.config, "secrets", lambda: {"DISCORD_WEBHOOK_URL": "https://discord.test/hook"})
    monkeypatch.setattr(
        main.config,
        "settings",
        lambda: {
            "discord": {"enabled": True},
            "email": {"enabled": False},
            "sms": {"enabled": False},
            "suppress_when_empty": True,
            "prune_after_days": 120,
        },
    )
    monkeypatch.setattr(main.discord_notify, "send_discord", lambda jobs, secrets, cfg: send_result)
    return state_path


def test_run_does_not_mark_seen_when_discord_fails(monkeypatch, tmp_path):
    state_path = _patch_run(monkeypatch, tmp_path, False)
    rc = main.run(False, True, True, True, None)
    assert rc == 1
    assert not state_path.exists()


def test_run_marks_seen_when_discord_succeeds(monkeypatch, tmp_path):
    state_path = _patch_run(monkeypatch, tmp_path, True)
    rc = main.run(False, True, True, True, None)
    assert rc == 0
    assert state_path.exists()
    assert "Acme" in state_path.read_text()

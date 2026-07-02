"""Filter behaviour against the real config/filters.yaml."""

from src import config
from src.filters import passes
from src.models import Job


def _job(title, locations=None, **kw):
    return Job(
        company=kw.pop("company", "Acme"),
        title=title,
        url=kw.pop("url", f"https://example.com/{abs(hash(title)) % 10000}"),
        locations=locations or [],
        **kw,
    )


F = config.filters()


def test_swe_summer_intern_rejected():
    j = _job("Software Engineer Intern", ["New York, NY"])
    assert not passes(j, F)


def test_quant_intern_classified_as_quant():
    j = _job("Quantitative Trading Intern", ["Chicago, IL"])
    assert passes(j, F)
    assert j.category == "quant"


def test_consulting_roles_rejected():
    j = _job("Associate Consultant, New Grad", ["Boston, MA"])
    assert not passes(j, F)


def test_consulting_intern_rejected():
    j = _job("Technology Analyst Intern", ["Boston, MA"])
    assert not passes(j, F)


def test_fulltime_senior_role_rejected():
    j = _job("Senior Software Engineer", ["San Francisco, CA"])
    assert not passes(j, F)


def test_new_grad_fulltime_kept():
    j = _job("Software Engineer, New Grad", ["Seattle, WA"])
    assert passes(j, F)
    assert j.category == "swe"


def test_generic_fulltime_swe_rejected():
    j = _job("Software Engineer I, Full-Time", ["Seattle, WA"])
    assert not passes(j, F)


def test_early_career_swe_kept():
    j = _job("Software Engineer, Early Career", ["Seattle, WA"])
    assert passes(j, F)
    assert j.category == "swe"


def test_software_engineer_ii_rejected():
    j = _job("Software Engineer II", ["Seattle, WA"])
    assert not passes(j, F)


def test_software_engineer_ii_early_career_rejected():
    j = _job("Software Engineer II, Early Career", ["Seattle, WA"])
    assert not passes(j, F)


def test_non_us_location_rejected():
    j = _job("Software Engineer, New Grad", ["London, UK"])
    assert not passes(j, F)


def test_canada_rejected():
    j = _job("Software Developer, New Grad", ["Toronto, Canada"])
    assert not passes(j, F)


def test_unknown_location_kept():
    j = _job("Software Engineer, New Grad")
    assert passes(j, F)  # keep_when_location_unknown: true


def test_multi_location_with_us_option_kept():
    j = _job("Software Engineer, New Grad", ["London, UK", "New York, NY"])
    assert passes(j, F)


def test_non_category_intern_rejected():
    j = _job("Marketing Intern", ["New York, NY"])
    assert not passes(j, F)


def test_out_of_window_year_rejected():
    j = _job("Quantitative Trading Intern, Summer 2025", ["Austin, TX"])
    assert not passes(j, F)


def test_2026_url_rejected():
    j = _job(
        "Software Engineer, New Grad",
        ["Seattle, WA"],
        url="https://example.com/jobs/software-engineer-new-grad-2026",
    )
    assert not passes(j, F)


def test_2026_title_rejected():
    j = _job("Software Engineer, New Grad 2026", ["Seattle, WA"])
    assert not passes(j, F)


def test_non_quant_coop_rejected():
    j = _job("Software Engineering Co-op", ["Boston, MA"])
    assert not passes(j, F)


def test_remote_kept():
    j = _job("Software Engineer, New Grad", ["Remote"])
    assert passes(j, F)

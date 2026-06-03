from datetime import datetime, timedelta

import pytest

from engines.dna_builder import (DEFAULT_BUSINESS_AGE_MONTHS, MATURITY_GATES,
                                 _business_age_months,
                                 build_compliance_dna)


def test_business_age_defaults_to_24_when_missing():
    assert _business_age_months(None) == DEFAULT_BUSINESS_AGE_MONTHS
    assert _business_age_months("") == DEFAULT_BUSINESS_AGE_MONTHS


def test_business_age_handles_garbage_input():
    assert _business_age_months("not-a-date") == DEFAULT_BUSINESS_AGE_MONTHS


def test_business_age_months_is_calendar_difference():
    eighteen_months_ago = (datetime.utcnow() - timedelta(days=18 * 30)).isoformat()
    months = _business_age_months(eighteen_months_ago)
    # Some month rounding tolerance
    assert 17 <= months <= 19


def test_maturity_gate_table_has_expected_keys():
    for freq in ("one_time", "monthly", "quarterly", "annual"):
        assert freq in MATURITY_GATES


# ── async DNA test with a fake mongo ──────────────────────────────────────────

class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d
        return gen()


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, query):
        return _FakeCursor(self._docs)


class _FakeDB:
    def __init__(self, corpus):
        self.regulatory_corpus = _FakeCollection(corpus)


@pytest.mark.asyncio
async def test_dna_filters_by_age_gate():
    """An annual-frequency reg should be skipped for a 2-month-old business."""
    corpus = [
        {
            "_id": "reg_annual",
            "name": "Annual ROC Filing",
            "category": "companies_act",
            "frequency": "annual",
            "deadline_rule": "by Sep 30",
            "complexity": 3,
            "max_penalty_inr": 100000,
            "depends_on": [],
            "applicable_to": {"industries": ["all"], "min_employees": 0,
                              "min_turnover_inr": 0, "registrations_required": []},
        },
        {
            "_id": "reg_monthly",
            "name": "Monthly GST Return",
            "category": "taxation",
            "frequency": "monthly",
            "deadline_rule": "20th",
            "complexity": 2,
            "max_penalty_inr": 50000,
            "depends_on": [],
            "applicable_to": {"industries": ["all"], "min_employees": 0,
                              "min_turnover_inr": 0, "registrations_required": []},
        },
    ]
    two_months_ago = (datetime.utcnow() - timedelta(days=60)).isoformat()
    dna = await build_compliance_dna(
        _FakeDB(corpus),
        "biz1",
        {"industry": "retail", "employee_count": 1, "annual_turnover_inr": 0,
         "registrations": [], "incorporation_date": two_months_ago},
    )
    names = [o["name"] for o in dna["applicable_obligations"]]
    assert "Monthly GST Return" in names
    assert "Annual ROC Filing" not in names  # gated by 12-month maturity
    assert dna["business_age_months"] >= 1

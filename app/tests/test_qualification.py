import pytest

from app.agent.tools.lead_scoring import compute_lead_score
from app.models.schemas import LeadScoreIn, IntentType, LeadStatus


def test_hot_lead():
    result = compute_lead_score(LeadScoreIn(
        budget=100000,
        timeline="immediate",
        industry="technology",
        problem_statement="We need a comprehensive CRM platform to manage our growing sales pipeline and customer relationships across multiple regions.",
        intent=IntentType.PURCHASE,
    ))
    assert result.score >= 0.7
    assert result.status == LeadStatus.HOT


def test_warm_lead():
    result = compute_lead_score(LeadScoreIn(
        budget=15000,
        timeline="this month",
        intent=IntentType.INFORMATION,
    ))
    assert 0.3 <= result.score < 0.65
    assert result.status == LeadStatus.WARM


def test_cold_lead():
    result = compute_lead_score(LeadScoreIn(
        budget=1000,
        timeline="6 months",
        intent=IntentType.UNKNOWN,
    ))
    assert result.score < 0.3
    assert result.status == LeadStatus.COLD


def test_real_estate_icp_industry_bonus():
    """Real estate and insurance get the 0.20 target-industry bucket."""
    result = compute_lead_score(LeadScoreIn(
        budget=50000,
        timeline="immediate",
        industry="real estate",
        intent=IntentType.PURCHASE,
    ))
    # With budget=50000 (0.30) + timeline=immediate (0.20) + rc industry (0.20)
    # + purchase intent (0.15) = 0.85, so 0.20 must have been contributed
    assert result.score >= 0.7
    assert "ICP industry" in result.reasoning


def test_insurance_icp_industry_bonus():
    """Insurance synonyms also get the 0.20 bucket."""
    result = compute_lead_score(LeadScoreIn(
        budget=10000,
        timeline="next month",
        industry="insurance agency",
        intent=IntentType.INFORMATION,
    ))
    # budget=10000 (0.20) + timeline=next month (0.15) + insurance (0.20)
    # + intent=information (0.05) = 0.60
    assert result.score >= 0.50
    assert "ICP industry" in result.reasoning


def test_secondary_industry_gets_lower_bonus():
    """Non-ICP industries (e.g. technology) get only 0.05."""
    result_icp = compute_lead_score(LeadScoreIn(
        budget=50000, timeline="immediate", industry="real estate",
        intent=IntentType.PURCHASE,
    ))
    result_secondary = compute_lead_score(LeadScoreIn(
        budget=50000, timeline="immediate", industry="technology",
        intent=IntentType.PURCHASE,
    ))
    # ICP gets 0.20, secondary gets 0.05 — delta of 0.15
    assert result_icp.score == pytest.approx(result_secondary.score + 0.15, abs=0.01)


def test_edge_cases():
    result = compute_lead_score(LeadScoreIn(
        budget=None,
        timeline=None,
        intent=IntentType.UNKNOWN,
    ))
    assert result.score >= 0
    assert result.score <= 1.0

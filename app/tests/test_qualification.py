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


def test_edge_cases():
    result = compute_lead_score(LeadScoreIn(
        budget=None,
        timeline=None,
        intent=IntentType.UNKNOWN,
    ))
    assert result.score >= 0
    assert result.score <= 1.0

import re
from app.config.settings import settings
from app.models.schemas import LeadScoreIn, LeadScoreOut, LeadStatus


# ── Vertical budget bands ──────────────────────────────────────────

_BUDGET_BANDS: dict[str, list[tuple[float, float]]] = {
    # (min, weight) — first matching band wins
    "generic": [
        (50_000, 0.30),
        (10_000, 0.20),
        (0, 0.05),
    ],
    "real_estate": [
        (3_000_000, 0.35),   # >= 30L
        (1_000_000, 0.25),   # >= 10L
        (500_000, 0.15),     # >= 5L
        (0, 0.05),
    ],
    "insurance": [
        (150, 0.30),    # $150+/mo
        (75, 0.20),     # $75+/mo
        (0, 0.05),
    ],
}


# ── Timeline / urgency (regex-based) ──────────────────────────────

_URGENCY_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\b(immediate|asap|right\s*away|urgent|now)\b", re.I), 0.20),
    (re.compile(r"\b(this\s*month|within\s*\d+\s*days?)\b", re.I), 0.18),
    (re.compile(r"\b(next\s*month|within\s*\d+\s*weeks?)\b", re.I), 0.15),
    (re.compile(r"\b(this\s*quarter|in\s*\d+\s*months?)\b", re.I), 0.10),
    (re.compile(r"\b(next\s*quarter|2\s*months?)\b", re.I), 0.05),
    (re.compile(r"\b(\d+\s*months?|half\s*year|6\s*months)\b", re.I), 0.02),
]

_INDIVIDUAL_VERTICAL_SIGNALS: dict[str, float] = {
    "real_estate": 0.15,
    "insurance": 0.15,
}


def _score_budget(budget: float | None, vertical: str) -> tuple[float, str]:
    if budget is None:
        return 0.0, "Budget unknown"
    bands = _BUDGET_BANDS.get(vertical, _BUDGET_BANDS["generic"])
    for threshold, weight in bands:
        if budget >= threshold:
            return weight, f"Budget: {budget}"
    return 0.05, f"Budget: {budget}"


def _score_timeline(timeline: str | None) -> tuple[float, str]:
    if not timeline:
        return 0.0, "Timeline unknown"
    tl = timeline.lower().strip()
    for pattern, weight in _URGENCY_PATTERNS:
        if pattern.search(tl):
            return weight, f"Timeline: {tl}"
    return 0.02, f"Timeline: {tl} (unrecognised)"


def _score_problem(problem_statement: str | None) -> tuple[float, str]:
    if not problem_statement:
        return 0.0, "Problem unknown"
    length = len(problem_statement)
    if length >= 100:
        return 0.15, "Well-defined problem"
    if length >= 30:
        return 0.08, "Partially defined problem"
    return 0.02, "Vague problem"


def _score_intent(intent: str) -> tuple[float, str]:
    scores = {"purchase": 0.15, "sell": 0.15, "information": 0.05,
              "support": 0.02, "partnership": 0.08, "unknown": 0.02}
    weight = scores.get(intent, 0.02)
    return weight, f"Intent: {intent}"


def compute_lead_score(data: LeadScoreIn) -> LeadScoreOut:
    score = 0.0
    reasons = []

    v = data.vertical or "generic"
    lt = data.lead_type
    is_individual = lt == "individual"

    # Budget (vertical-aware)
    bw, br = _score_budget(data.budget, v)
    score += bw
    reasons.append(br)

    # Timeline (regex-based, all verticals)
    tw, tr = _score_timeline(data.timeline)
    score += tw
    reasons.append(tr)

    # Industry / vertical fit
    if data.industry and v == "generic" and not is_individual:
        ind = data.industry.lower()
        _ICP_INDUSTRIES = {
            "real estate", "realty", "brokerage", "real estate brokerage",
            "insurance", "insurance agency", "independent insurance",
        }
        _SECONDARY_INDUSTRIES = {
            "technology", "saas", "software", "fintech", "healthtech",
            "healthcare", "manufacturing", "logistics", "ecommerce", "retail",
        }
        if ind in _ICP_INDUSTRIES:
            score += 0.20
            reasons.append(f"ICP industry: {data.industry}")
        elif ind in _SECONDARY_INDUSTRIES:
            score += 0.05
            reasons.append(f"Secondary industry: {data.industry}")
        else:
            reasons.append(f"Non-target industry: {data.industry}")
    elif is_individual and v in _INDIVIDUAL_VERTICAL_SIGNALS:
        bump = _INDIVIDUAL_VERTICAL_SIGNALS[v]
        score += bump
        reasons.append(f"Individual vertical signal ({v}): +{bump}")
    elif data.industry:
        reasons.append(f"Lead context: {data.industry}")
    else:
        reasons.append("Industry unknown")

    # Problem clarity
    pw, pr = _score_problem(data.problem_statement)
    score += pw
    reasons.append(pr)

    # Intent
    iw, ir = _score_intent(data.intent.value if hasattr(data.intent, 'value') else str(data.intent))
    score += iw
    reasons.append(ir)

    score = min(score, 1.0)

    if score >= settings.qualification_threshold_hot:
        status = LeadStatus.HOT
    elif score >= settings.qualification_threshold_warm:
        status = LeadStatus.WARM
    else:
        status = LeadStatus.COLD

    return LeadScoreOut(score=round(score, 2), status=status, reasoning="; ".join(reasons))

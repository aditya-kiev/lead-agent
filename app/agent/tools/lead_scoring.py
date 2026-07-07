from app.models.schemas import LeadScoreIn, LeadScoreOut, LeadStatus


_TARGET_INDUSTRIES = {
    "technology", "saas", "software", "fintech", "healthtech",
    "healthcare", "manufacturing", "logistics", "ecommerce", "retail",
}


def compute_lead_score(data: LeadScoreIn) -> LeadScoreOut:
    score = 0.0
    reasons = []

    if data.budget is not None:
        if data.budget >= 50000:
            score += 0.30
            reasons.append("Budget is sufficient")
        elif data.budget >= 10000:
            score += 0.20
            reasons.append("Budget is moderate")
        else:
            score += 0.05
            reasons.append("Budget is low")
    else:
        reasons.append("Budget unknown")

    urgency_map = {
        "immediate": 0.20, "this month": 0.18, "next month": 0.15,
        "this quarter": 0.10, "next quarter": 0.05, "6 months": 0.02,
    }
    if data.timeline:
        tl = data.timeline.lower().strip()
        score += urgency_map.get(tl, 0.02)
        reasons.append(f"Timeline: {tl}")
    else:
        reasons.append("Timeline unknown")

    if data.industry and data.industry.lower() in _TARGET_INDUSTRIES:
        score += 0.20
        reasons.append(f"Target industry: {data.industry}")
    elif data.industry:
        score += 0.05
        reasons.append(f"Non-target industry: {data.industry}")
    else:
        reasons.append("Industry unknown")

    if data.problem_statement:
        problem_len = len(data.problem_statement)
        if problem_len >= 100:
            score += 0.15
            reasons.append("Well-defined problem")
        elif problem_len >= 30:
            score += 0.08
            reasons.append("Partially defined problem")
        else:
            score += 0.02
            reasons.append("Vague problem")
    else:
        reasons.append("Problem unknown")

    if data.intent:
        intent_scores = {"purchase": 0.15, "information": 0.05, "support": 0.02, "partnership": 0.08, "unknown": 0.02}
        score += intent_scores.get(data.intent, 0.02)
        reasons.append(f"Intent: {data.intent}")
    else:
        reasons.append("Intent unknown")

    score = min(score, 1.0)

    if score >= 0.7:
        status = LeadStatus.HOT
    elif score >= 0.3:
        status = LeadStatus.WARM
    else:
        status = LeadStatus.COLD

    return LeadScoreOut(score=round(score, 2), status=status, reasoning="; ".join(reasons))

"""Prompt templates."""

EXTRACT_PROMPT = """Analyze this support ticket:

{ticket_content}

Extract JSON with: category, product_area, sentiment, priority, themes (list), summary

Categories: bug, feature_request, question, complaint
Sentiments: positive, neutral, negative, frustrated
Priorities: low, medium, high, critical

Return ONLY valid JSON."""


SUMMARIZE_PROMPT = """Summarize today's support tickets.

Stats:
- Total tickets: {ticket_count}
- Categories: {categories}
- Top themes: {top_themes}

Sample tickets:
{samples}

Yesterday's summary: {previous_summary}

Generate JSON with:
- key_themes: list of 5 most important themes
- trend_analysis: how this compares to yesterday
- critical_issues: anything requiring immediate attention

Return ONLY valid JSON."""


REPORT_PROMPT = """Generate an executive report optimized for product team engagement and action.

Last 7 days summaries:
{summaries}

Create a JSON report with the following structure:

1. executive_summary:
   - Start with the most critical insight (what changed and why it matters)
   - Include key metrics with directional indicators (↑↓)
   - End with business impact (customer satisfaction, revenue risk, brand reputation)
   - Keep to 3-4 sentences max

2. health_snapshot:
   - overall_health: "critical" | "concerning" | "stable" | "improving" (with brief justification)
   - ticket_volume_trend: numerical change with percentage
   - complaint_rate_trend: numerical change with percentage
   - top_3_drivers: list of issue types driving the most volume

3. key_insights (5 insights, prioritized by impact):
   For each insight provide:
   - insight: the finding itself
   - severity: "critical" | "high" | "medium" | "low"
   - evidence: specific data points or patterns supporting this
   - customer_impact: how this affects customer experience

4. recommended_actions (3-5 actions, prioritized):
   For each action provide:
   - action: specific, actionable task
   - priority: "immediate" | "this_week" | "this_month"
   - estimated_impact: "high" | "medium" | "low" - expected reduction in ticket volume or complaint rate
   - suggested_owner: which team should own this (e.g., "Engineering", "Operations", "Product", "Support")
   - success_metrics: how to measure if this worked (specific KPIs)

5. customer_voice:
   - Include 2-3 verbatim ticket quotes or paraphrased examples that illustrate the most critical issues
   - These should be emotionally resonant and help teams understand real customer pain

6. week_over_week_comparison:
   - Highlight what improved, what deteriorated, and what stayed the same
   - Focus on actionable changes, not just descriptive stats

Guidelines:
- Use specific numbers over vague terms ("42% complaint rate" not "high complaints")
- Frame insights around customer impact and business risk
- Make actions concrete enough that teams can start immediately
- Prioritize ruthlessly - what matters MOST right now
- Use urgency appropriately (not everything is critical)

Return ONLY valid JSON."""


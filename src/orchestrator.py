"""Pipeline orchestration and layer coordination."""
import asyncio
from collections import Counter
from datetime import date, datetime, timedelta

# Support both direct execution and module import
try:
    from .models import TicketAnalysis, DailySummary, Report
    from .prompts import EXTRACT_PROMPT, SUMMARIZE_PROMPT, REPORT_PROMPT
    from .client import APIClient, parse_json
    from .cache import DateOrganizedCache, FileCache
except ImportError:
    from models import TicketAnalysis, DailySummary, Report
    from prompts import EXTRACT_PROMPT, SUMMARIZE_PROMPT, REPORT_PROMPT
    from client import APIClient, parse_json
    from cache import DateOrganizedCache, FileCache


class Extractor:
    """Layer 1: Extract structured data from individual tickets."""

    def __init__(self, cache_dir, api_client: APIClient):
        self.cache = DateOrganizedCache(cache_dir)
        self.api = api_client

    async def extract_ticket(
        self,
        ticket_id: str,
        ticket_content: str,
        ticket_date: date,
        semaphore: asyncio.Semaphore
    ) -> TicketAnalysis:
        """Extract analysis from a single ticket with caching."""
        # Check cache
        if self.cache.exists_dated(ticket_id, ticket_date):
            cached = self.cache.get_dated(
                ticket_id,
                ticket_date,
                lambda text: TicketAnalysis.model_validate_json(text)
            )
            if cached:
                return cached

        # Call API
        prompt = EXTRACT_PROMPT.format(ticket_content=ticket_content)
        content = await self.api.call(prompt, max_tokens=1024, semaphore=semaphore)

        # Parse and save
        data = parse_json(content)
        analysis = TicketAnalysis(ticket_id=ticket_id, **data)
        self.cache.save_dated(
            ticket_id,
            ticket_date,
            analysis,
            lambda obj: obj.model_dump_json(indent=2)
        )

        return analysis

    async def extract_batch(
        self,
        tickets: list[dict],
        max_concurrent: int = 10
    ) -> list[TicketAnalysis]:
        """Extract all tickets with progress tracking."""
        semaphore = asyncio.Semaphore(max_concurrent)
        total = len(tickets)
        completed = 0

        async def extract_with_progress(ticket: dict) -> TicketAnalysis:
            nonlocal completed
            try:
                ticket_date = datetime.fromisoformat(
                    ticket["created_at"].replace("Z", "+00:00")
                ).date()
            except (ValueError, AttributeError):
                ticket_date = date.today()

            try:
                result = await self.extract_ticket(
                    ticket["id"], ticket["content"], ticket_date, semaphore
                )
                completed += 1
                print(f"  Progress: {completed}/{total} tickets", end="\r")
                return result
            except Exception as e:
                completed += 1
                print(f"\n  Warning: Failed to process {ticket['id']}: {e}")
                print(f"  Progress: {completed}/{total} tickets", end="\r")
                # Return placeholder for failed tickets
                return TicketAnalysis(
                    ticket_id=ticket["id"],
                    category="error",
                    product_area="unknown",
                    sentiment="neutral",
                    priority="low",
                    themes=[],
                    summary=f"Failed to extract: {str(e)}"
                )

        results = await asyncio.gather(*[extract_with_progress(t) for t in tickets])
        print(f"  Progress: {completed}/{total} tickets")
        return results


class Summarizer:
    """Layer 2: Generate daily summaries from extracted analyses."""

    def __init__(self, cache_dir, api_client: APIClient):
        self.cache = FileCache(cache_dir)
        self.api = api_client

    async def summarize_day(
        self,
        target_date: date,
        analyses: list[TicketAnalysis]
    ) -> DailySummary:
        """Generate summary for a single day with caching."""
        date_key = target_date.isoformat()

        # Check cache
        if self.cache.exists(date_key):
            cached = self.cache.get(
                date_key,
                lambda text: DailySummary.model_validate_json(text)
            )
            if cached:
                return cached

        # Aggregate statistics
        categories = Counter(a.category for a in analyses)
        all_themes = [theme for a in analyses for theme in a.themes]
        top_themes = Counter(all_themes).most_common(10)

        # Get context from yesterday
        yesterday = target_date - timedelta(days=1)
        yesterday_key = yesterday.isoformat()
        previous_summary = "No previous summary"
        if self.cache.exists(yesterday_key):
            prev = self.cache.get(
                yesterday_key,
                lambda text: DailySummary.model_validate_json(text)
            )
            if prev:
                previous_summary = prev.trend_analysis

        # Sample tickets for context
        samples = "\n".join([
            f"- [{a.priority}] {a.category}: {a.summary}"
            for a in analyses[:15]
        ])

        # Call API
        prompt = SUMMARIZE_PROMPT.format(
            ticket_count=len(analyses),
            categories=dict(categories),
            top_themes=dict(top_themes),
            samples=samples,
            previous_summary=previous_summary
        )
        content = await self.api.call(prompt, max_tokens=2048)

        # Parse and normalize
        data = parse_json(content)
        data = self._normalize(data)
        summary = DailySummary(date=target_date, ticket_count=len(analyses), **data)

        # Cache it
        self.cache.save(
            date_key,
            summary,
            lambda obj: obj.model_dump_json(indent=2)
        )

        return summary

    @staticmethod
    def _normalize(data: dict) -> dict:
        """Normalize LLM response to handle variations in structure."""
        normalized = data.copy()

        # Normalize trend_analysis
        if "trend_analysis" in normalized:
            trend = normalized["trend_analysis"]
            if isinstance(trend, dict):
                normalized["trend_analysis"] = (
                    trend.get("note") or trend.get("text") or trend.get("analysis") or str(trend)
                )
            elif not isinstance(trend, str):
                normalized["trend_analysis"] = str(trend)

        # Normalize critical_issues
        if "critical_issues" in normalized:
            issues = normalized["critical_issues"]
            if isinstance(issues, list):
                normalized_issues = []
                for issue in issues:
                    if isinstance(issue, dict):
                        normalized_issues.append(
                            issue.get("issue") or issue.get("text") or issue.get("description") or str(issue)
                        )
                    else:
                        normalized_issues.append(str(issue))
                normalized["critical_issues"] = normalized_issues

        # Normalize key_themes
        if "key_themes" in normalized:
            themes = normalized["key_themes"]
            if isinstance(themes, list):
                normalized["key_themes"] = [
                    theme.get("theme") or str(theme) if isinstance(theme, dict) else str(theme)
                    for theme in themes
                ]

        return normalized


class Reporter:
    """Layer 3: Generate executive reports from summaries."""

    def __init__(self, cache_dir, api_client: APIClient):
        self.cache = FileCache(cache_dir)
        self.api = api_client

    async def generate_report(self, summaries: list[DailySummary]) -> Report:
        """Generate executive report from multiple daily summaries."""
        # Format summaries for prompt
        summaries_text = "\n\n".join([
            f"Date: {s.date}\nTickets: {s.ticket_count}\n"
            f"Themes: {', '.join(s.key_themes)}\n"
            f"Analysis: {s.trend_analysis}"
            for s in summaries
        ])

        # Call API
        prompt = REPORT_PROMPT.format(summaries=summaries_text)
        content = await self.api.call(prompt, max_tokens=4096)

        # Parse and normalize
        data = parse_json(content)
        data = self._normalize(data)

        start = summaries[0].date
        end = summaries[-1].date
        report = Report(period=f"{start} to {end}", **data)

        # Cache it
        report_key = f"report_{start}_{end}"
        self.cache.save(
            report_key,
            report,
            lambda obj: obj.model_dump_json(indent=2)
        )

        return report

    @staticmethod
    def _normalize(data: dict) -> dict:
        """Normalize LLM response to handle variations in structure."""
        normalized = data.copy()

        # Normalize executive_summary
        if "executive_summary" in normalized:
            summary = normalized["executive_summary"]
            if isinstance(summary, dict):
                normalized["executive_summary"] = (
                    summary.get("summary") or summary.get("text") or summary.get("note") or str(summary)
                )
            elif not isinstance(summary, str):
                normalized["executive_summary"] = str(summary)

        # Normalize health_snapshot
        if "health_snapshot" in normalized:
            hs = normalized["health_snapshot"]
            if isinstance(hs, dict):
                for field in ["overall_health", "ticket_volume_trend", "complaint_rate_trend"]:
                    if field in hs and not isinstance(hs[field], str):
                        hs[field] = str(hs[field])

                if "top_3_drivers" in hs and isinstance(hs["top_3_drivers"], list):
                    hs["top_3_drivers"] = [
                        driver.get("driver") or str(driver) if isinstance(driver, dict) else str(driver)
                        for driver in hs["top_3_drivers"]
                    ]

        # Normalize key_insights
        if "key_insights" in normalized:
            insights = normalized["key_insights"]
            if isinstance(insights, list):
                normalized_insights = []
                for insight in insights:
                    if isinstance(insight, dict):
                        evidence = insight.get("evidence") or insight.get("text") or ""
                        if isinstance(evidence, (list, dict)):
                            evidence = str(evidence)

                        customer_impact = insight.get("customer_impact") or insight.get("impact") or ""
                        if isinstance(customer_impact, (list, dict)):
                            customer_impact = str(customer_impact)

                        normalized_insights.append({
                            "insight": insight.get("insight") or str(insight),
                            "severity": insight.get("severity") or "medium",
                            "evidence": evidence,
                            "customer_impact": customer_impact
                        })
                    else:
                        normalized_insights.append({
                            "insight": str(insight),
                            "severity": "medium",
                            "evidence": "",
                            "customer_impact": ""
                        })
                normalized["key_insights"] = normalized_insights

        # Normalize recommended_actions
        if "recommended_actions" in normalized:
            actions = normalized["recommended_actions"]
            if isinstance(actions, list):
                normalized_actions = []
                for action in actions:
                    if isinstance(action, dict):
                        success_metrics = action.get("success_metrics") or action.get("metrics") or ""
                        if isinstance(success_metrics, (list, dict)):
                            success_metrics = str(success_metrics)

                        normalized_actions.append({
                            "action": action.get("action") or str(action),
                            "priority": action.get("priority") or "this_week",
                            "estimated_impact": action.get("estimated_impact") or "medium",
                            "suggested_owner": action.get("suggested_owner") or action.get("owner") or "",
                            "success_metrics": success_metrics
                        })
                    else:
                        normalized_actions.append({
                            "action": str(action),
                            "priority": "this_week",
                            "estimated_impact": "medium",
                            "suggested_owner": "",
                            "success_metrics": ""
                        })
                normalized["recommended_actions"] = normalized_actions

        # Normalize customer_voice
        if "customer_voice" in normalized:
            cv = normalized["customer_voice"]
            if isinstance(cv, dict):
                if "quotes" in cv and isinstance(cv["quotes"], list):
                    cv["quotes"] = [
                        quote.get("quote") or str(quote) if isinstance(quote, dict) else str(quote)
                        for quote in cv["quotes"]
                    ]
                else:
                    cv["quotes"] = []
            else:
                normalized["customer_voice"] = {"quotes": []}

        # Normalize week_over_week_comparison
        if "week_over_week_comparison" in normalized:
            wowc = normalized["week_over_week_comparison"]
            if isinstance(wowc, dict):
                for field in ["improved", "deteriorated", "stayed_same"]:
                    if field in wowc and isinstance(wowc[field], list):
                        wowc[field] = [
                            item.get("item") or str(item) if isinstance(item, dict) else str(item)
                            for item in wowc[field]
                        ]
                    else:
                        wowc[field] = []

        return normalized

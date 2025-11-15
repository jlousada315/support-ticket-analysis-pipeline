"""Support ticket analysis pipeline - 3 layers (extract, summarize, report)."""
import asyncio
from datetime import date, datetime
from pathlib import Path

# Support both direct script execution and module import
try:
    from .csv_loader import load_tickets, get_date_range
    from .orchestrator import Extractor, Summarizer, Reporter
    from .client import APIClient
    from .models import Report
except ImportError:
    from csv_loader import load_tickets, get_date_range
    from orchestrator import Extractor, Summarizer, Reporter
    from client import APIClient
    from models import Report


DATA_DIR = Path("data")


def _format_value(value) -> str:
    """Format value for markdown output."""
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items())
    elif isinstance(value, list):
        return ", ".join(str(i) if not isinstance(i, (dict, list)) else _format_value(i) for i in value) or "N/A"
    return str(value).strip()


def _report_to_markdown(report: Report) -> str:
    """Convert report to markdown format."""
    lines = [
        "# Support Ticket Analysis Report",
        f"**Period:** {report.period}\n",
        "## Executive Summary",
        report.executive_summary,
        "",
        "## Health Snapshot"
    ]

    hs = report.health_snapshot
    lines.extend([
        f"- **Overall Health:** {hs.overall_health}",
        f"- **Ticket Volume Trend:** {_format_value(hs.ticket_volume_trend)}",
        f"- **Complaint Rate Trend:** {_format_value(hs.complaint_rate_trend)}",
        "- **Top 3 Drivers:**",
        *[f"  - {_format_value(d)}" for d in hs.top_3_drivers],
        "",
        "## Key Insights"
    ])

    for i, insight in enumerate(report.key_insights, 1):
        lines.extend([
            f"### Insight {i}: {insight.insight}",
            f"- **Severity:** {insight.severity}",
            f"- **Evidence:** {_format_value(insight.evidence)}",
            f"- **Customer Impact:** {_format_value(insight.customer_impact)}",
            ""
        ])

    lines.append("## Recommended Actions")
    for i, action in enumerate(report.recommended_actions, 1):
        lines.extend([
            f"### Action {i}: {action.action}",
            f"- **Priority:** {action.priority}",
            f"- **Estimated Impact:** {action.estimated_impact}",
            f"- **Suggested Owner:** {action.suggested_owner}",
            f"- **Success Metrics:** {_format_value(action.success_metrics)}",
            ""
        ])

    if report.customer_voice.quotes:
        lines.append("## Customer Voice")
        lines.extend([f"> {_format_value(q)}" for q in report.customer_voice.quotes])
        lines.append("")

    lines.append("## Week-over-Week Comparison")
    wowc = report.week_over_week_comparison
    if wowc.improved:
        lines.append("### Improved")
        lines.extend([f"- {_format_value(i)}" for i in wowc.improved])
        lines.append("")
    if wowc.deteriorated:
        lines.append("### Deteriorated")
        lines.extend([f"- {_format_value(i)}" for i in wowc.deteriorated])
        lines.append("")
    if wowc.stayed_same:
        lines.append("### Stayed the Same")
        lines.extend([f"- {_format_value(i)}" for i in wowc.stayed_same])
        lines.append("")

    return "\n".join(lines)


async def run_pipeline(start_date: date | None = None, end_date: date | None = None):
    """Run the complete 3-layer pipeline: extract → summarize → report."""
    print("=== Support Ticket Analysis Pipeline ===\n")

    # Setup
    csv_file = DATA_DIR / "sofa-sogood.csv"
    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        return

    # Determine date range
    if start_date is None or end_date is None:
        print("Determining date range from CSV...")
        default_start, default_end = get_date_range(csv_file)
        start_date = start_date or default_start
        end_date = end_date or default_end
        print(f"Date range: {start_date} to {end_date} (last 2 days)\n")

    # Load tickets
    print(f"Loading tickets from {csv_file}...")
    tickets = load_tickets(csv_file, start_date, end_date)
    print(f"Loaded {len(tickets)} tickets\n")

    # Setup layers
    api = APIClient()
    extractor = Extractor(DATA_DIR / "analyses", api)
    summarizer = Summarizer(DATA_DIR / "summaries", api)
    reporter = Reporter(DATA_DIR / "reports", api)

    # Layer 1: Extract
    print("Extracting structured data from tickets...")
    analyses = await extractor.extract_batch(tickets)
    print(f"✓ Extracted {len(analyses)} analyses\n")

    # Layer 2: Summarize by date
    print("Generating daily summaries...")
    by_date = {}
    for ticket, analysis in zip(tickets, analyses):
        try:
            ticket_date = datetime.fromisoformat(
                ticket["created_at"].replace("Z", "+00:00")
            ).date()
        except (ValueError, AttributeError):
            ticket_date = date.today()
        by_date.setdefault(ticket_date, []).append(analysis)

    summaries = []
    for target_date, day_analyses in sorted(by_date.items()):
        summary = await summarizer.summarize_day(target_date, day_analyses)
        summaries.append(summary)
        print(f"✓ {target_date}: {summary.ticket_count} tickets")

    # Layer 3: Report
    if not summaries:
        print("No summaries generated.")
        return

    print("\nGenerating executive report...")
    report = await reporter.generate_report(summaries)
    print("✓ Report generated\n")

    # Save markdown
    print("Saving markdown report...")
    md_content = _report_to_markdown(report)
    start, end = report.period.split(" to ")
    md_file = DATA_DIR / "reports" / f"report_{start}_{end}.md"
    md_file.write_text(md_content)
    print(f"✓ Saved to {md_file}\n")

    # Display summary
    print("=" * 60)
    print("EXECUTIVE SUMMARY")
    print("=" * 60)
    print(report.executive_summary)
    print("\nHEALTH SNAPSHOT:")
    hs = report.health_snapshot
    print(f"  Overall Health: {hs.overall_health}")
    print(f"  Ticket Volume Trend: {hs.ticket_volume_trend}")
    print(f"  Complaint Rate Trend: {hs.complaint_rate_trend}")
    print(f"  Top 3 Drivers: {', '.join(hs.top_3_drivers)}")
    print("\nKEY INSIGHTS:")
    for i, insight in enumerate(report.key_insights, 1):
        print(f"{i}. [{insight.severity.upper()}] {insight.insight}")
    print("\nRECOMMENDED ACTIONS:")
    for i, action in enumerate(report.recommended_actions, 1):
        print(f"{i}. [{action.priority.upper()}] {action.action}")
        if action.suggested_owner:
            print(f"   Owner: {action.suggested_owner}")
    print("\nCUSTOMER VOICE:")
    for quote in report.customer_voice.quotes:
        print(f"  \"{quote}\"")
    print("=" * 60)
    print(f"Full report: {md_file}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_pipeline())

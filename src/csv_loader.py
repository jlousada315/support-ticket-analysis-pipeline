"""CSV data loading and parsing."""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


def get_date_range(csv_path: Path) -> tuple[date, date]:
    """Extract date range from CSV (latest and previous day)."""
    df = pd.read_csv(csv_path)

    dates = []
    for row in df.itertuples():
        try:
            dt = datetime.fromisoformat(str(row.ds).replace("Z", "+00:00"))
            dates.append(dt.date())
        except (ValueError, AttributeError):
            continue

    if not dates:
        raise ValueError("No valid dates found in CSV")

    latest_date = max(dates)
    previous_date = latest_date - timedelta(days=1)
    return previous_date, latest_date


def load_tickets(
    csv_path: Path,
    start_date: date | None = None,
    end_date: date | None = None
) -> list[dict]:
    """Load support tickets from CSV.

    Returns list of dicts with: id, content, created_at, metadata
    """
    df = pd.read_csv(csv_path)

    tickets = []
    for idx, row in df.iterrows():
        # Parse timestamp
        created_at_str = row["ds"]
        ticket_date = None
        if isinstance(created_at_str, str):
            try:
                dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                ticket_date = dt.date()
                created_at = dt.isoformat()
            except (ValueError, AttributeError):
                created_at = str(created_at_str)
        else:
            created_at = str(created_at_str)

        # Filter by date range if specified
        if start_date is not None and ticket_date is not None:
            if ticket_date < start_date:
                continue
        if end_date is not None and ticket_date is not None:
            if ticket_date > end_date:
                continue

        # Parse extra JSON
        extra_data = {}
        if pd.notna(row.get("extra")):
            try:
                extra_data = json.loads(row["extra"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Build ticket
        content = row.get("original_message", "")
        if pd.isna(content):
            content = ""

        ticket = {
            "id": f"ticket_{idx}",
            "content": str(content),
            "created_at": created_at,
            "metadata": extra_data,
        }
        tickets.append(ticket)

    return tickets

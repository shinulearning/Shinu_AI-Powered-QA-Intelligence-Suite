"""Helpers for loading historical defect data for risk analysis."""

import csv
import os
import re

DEFAULT_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resources",
    "historical_defects.csv",
)


def _extract_field(description, field_name):
    if not description:
        return ""
    match = re.search(
        rf"h3\.\s*{field_name}\s*\n+(.*?)(?:\n\s*h3\.|\Z)",
        description,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def load_historical_defects(csv_path=None, limit=10):
    csv_path = csv_path or DEFAULT_CSV_PATH

    if not os.path.exists(csv_path):
        return "No historical defect data available."

    defects = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Issue Type") != "Bug":
                continue
            description = row.get("Description", "")
            defects.append({
                "key": row.get("Issue key", ""),
                "summary": row.get("Summary", ""),
                "priority": row.get("Priority", ""),
                "status": row.get("Status", ""),
                "module": _extract_field(description, "Module") or "Unknown",
                "severity": _extract_field(description, "Severity") or "Unknown",
                "created": row.get("Created", ""),
            })
            if len(defects) >= limit:
                break

    if not defects:
        return "No historical defect data available."

    lines = ["Historical Defects:"]
    for d in defects:
        lines.append(
            f"- {d['key']}: {d['summary']} | Module: {d['module']} "
            f"| Severity: {d['severity']} | Priority: {d['priority']} "
            f"| Status: {d['status']} | Created: {d['created']}"
        )

    return "\n".join(lines)

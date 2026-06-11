"""Production Risk Intelligence engine.

Builds an executive-friendly Release Risk report (Release Risk Score, Top Risk
Areas, Potential Production Failures, Recommended Regression Areas, and a
Release Readiness recommendation) from three simple inputs:

* resources/historical_defects.csv  -- historical defect data (Jira export)
* resources/release_scope.txt       -- modules included in the current release
* resources/project_context.md      -- module risk profile (used to enrich
                                        reasons; only a small, hand-picked
                                        subset is referenced below)

All scoring uses simple, fixed, documented weights -- no ML models, no
external services. The output is returned as a plain dict (JSON-serialisable)
plus a human-readable text report via `format_report_text()`.
"""

import os

import pandas as pd

from utils.historical_defects import _extract_field

RESOURCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
DEFAULT_CSV_PATH = os.path.join(RESOURCES_DIR, "historical_defects.csv")
DEFAULT_RELEASE_SCOPE_PATH = os.path.join(RESOURCES_DIR, "release_scope.txt")


# ---------------------------------------------------------------------------
# Module risk configuration
#
# Derived from resources/project_context.md ("Production Risk Rules" and
# module "Risk Level" sections). Kept as a small explicit table so the
# scoring logic stays simple and easy to review/extend.
# ---------------------------------------------------------------------------
CATEGORY_CONFIG = {
    "Authentication": {
        "release_scope_match": ["authentication"],
        "defect_keywords": ["auth", "session", "login", "password", "permission", "role", "credential", "authority"],
        "context_risk_level": "Critical",
        "failure_scenarios": [
            {
                "name": "Permission Validation Failure",
                "keywords": ["permission", "authority", "role", "access"],
                "impact": "Unauthorized users may view or modify data and functions they should not have access to.",
            },
            {
                "name": "Session Management Failure",
                "keywords": ["session"],
                "impact": "Users may remain logged in after logout, or be unexpectedly logged out, exposing accounts.",
            },
            {
                "name": "Authentication / Login Failure",
                "keywords": ["login", "password", "credential", "authentication"],
                "impact": "Users may be unable to log in or reset passwords, blocking access to the application.",
            },
        ],
        "regression_areas": [
            {"area": "Login", "focus": "Valid/invalid credential handling and error messaging"},
            {"area": "Logout", "focus": "Session/token invalidation on logout"},
            {"area": "Session Management", "focus": "Idle timeout, token expiry, concurrent sessions"},
            {"area": "Role Validation", "focus": "Role-based access control across Viewer/Operator/Admin/Super Admin"},
        ],
    },
    "Equipment Synchronization": {
        "release_scope_match": ["equipment sync", "equipment synchronization", "synchronization", "equipment"],
        "defect_keywords": ["equipment", "sync", "synchroniz"],
        "context_risk_level": "High",
        "failure_scenarios": [
            {
                "name": "Data Synchronization Timeout",
                "keywords": ["sync", "synchroniz", "timeout"],
                "impact": "Equipment/customer data becomes inconsistent between the application and downstream systems.",
            },
            {
                "name": "Equipment Detail Mismatch",
                "keywords": ["equipment", "mismatch"],
                "impact": "Incorrect equipment specifications may lead to wrong operational decisions.",
            },
            {
                "name": "Duplicate Record Creation",
                "keywords": ["duplicate"],
                "impact": "Duplicate equipment/customer records cause reporting and reconciliation errors.",
            },
        ],
        "regression_areas": [
            {"area": "Full Synchronization", "focus": "End-to-end sync job completion and data accuracy"},
            {"area": "Incremental Synchronization", "focus": "Delta updates and timing"},
            {"area": "Equipment Master Data", "focus": "Equipment detail accuracy vs. master records"},
            {"area": "Retry Mechanisms", "focus": "Recovery behaviour after sync failure or timeout"},
        ],
    },
    "Notification Service": {
        "release_scope_match": ["notification"],
        "defect_keywords": ["notification", "email", "alert"],
        # Not yet documented in project_context.md - conservative default.
        "context_risk_level": "Medium",
        "failure_scenarios": [
            {
                "name": "Notification Delivery Failure",
                "keywords": ["notification", "email"],
                "impact": "Users miss critical status-change alerts, delaying response to issues.",
            },
        ],
        "regression_areas": [
            {"area": "Notification Triggers", "focus": "Status-change events fire notification jobs"},
            {"area": "Email Delivery", "focus": "End-to-end email delivery and templates"},
            {"area": "Notification Preferences", "focus": "User opt-in/opt-out settings are respected"},
        ],
    },
}

# Generic fallback used for release-scope modules that don't map to any of
# the categories above (keeps the report from crashing if release scope changes).
_FALLBACK_CATEGORY_TEMPLATE = {
    "defect_keywords": [],
    "context_risk_level": "Unknown",
    "failure_scenarios": [],
    "regression_areas": [],
}

SEVERITY_WEIGHTS = {"Critical": 1.0, "Major": 0.5, "Minor": 0.15, "Unknown": 0.15}

# Release Risk Score weights (each factor documented for explainability).
SCORE_BASE = 1.0
SCORE_HISTORICAL_VOLUME_WEIGHT = 1.0   # min(1.0, total_defects / 50)
SCORE_CRITICAL_WEIGHT = 1.0            # per Critical defect in release scope
SCORE_MAJOR_WEIGHT = 0.5               # per Major defect in release scope
SCORE_MINOR_WEIGHT = 0.15              # per Minor/Unknown defect in release scope
SCORE_MODULE_IN_SCOPE_WEIGHT = 0.2     # per module included in this release
SCORE_RECURRENCE_WEIGHT = 0.3          # per category with >= 2 historical defects

RISK_SCORE_MIN = 1.0
RISK_SCORE_MAX = 10.0

# Category-level risk score thresholds (sum of severity weights for a category).
_CATEGORY_RISK_THRESHOLDS = (
    (2.5, "Critical"),
    (1.0, "High"),
    (0.4, "Medium"),
)


def _release_risk_level(score):
    if score >= 8.5:
        return "Critical"
    if score >= 6.5:
        return "High"
    if score >= 4.0:
        return "Medium"
    return "Low"


def _category_risk_level(score):
    for threshold, level in _CATEGORY_RISK_THRESHOLDS:
        if score >= threshold:
            return level
    return "Low"


def load_release_scope(path=None):
    """Return the list of module names declared for the current release."""
    path = path or DEFAULT_RELEASE_SCOPE_PATH
    if not os.path.exists(path):
        return []

    modules = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("-"):
                modules.append(line.lstrip("-").strip())
    return modules


def load_defects(csv_path=None):
    """Return a DataFrame of all Bug rows with module/severity/priority extracted."""
    csv_path = csv_path or DEFAULT_CSV_PATH
    if not os.path.exists(csv_path):
        return pd.DataFrame(columns=["key", "summary", "module", "severity", "priority", "status", "created"])

    df = pd.read_csv(csv_path)
    df = df[df["Issue Type"] == "Bug"].copy()

    df["module"] = df["Description"].apply(lambda d: _extract_field(d, "Module") or "Unknown")
    df["severity"] = df["Description"].apply(lambda d: _extract_field(d, "Severity") or "Unknown")

    return pd.DataFrame({
        "key": df["Issue key"],
        "summary": df["Summary"],
        "module": df["module"],
        "severity": df["severity"],
        "priority": df["Priority"],
        "status": df["Status"],
        "created": df["Created"],
    })


def _resolve_categories(release_scope_modules):
    """Map each release-scope module name to a CATEGORY_CONFIG entry."""
    categories = {}
    for module_name in release_scope_modules:
        normalized = module_name.lower()
        matched_key = None
        for category_key, config in CATEGORY_CONFIG.items():
            if any(m in normalized or normalized in m for m in config["release_scope_match"]):
                matched_key = category_key
                break

        if matched_key:
            categories[matched_key] = {"release_scope_name": module_name, **CATEGORY_CONFIG[matched_key]}
        else:
            fallback = dict(_FALLBACK_CATEGORY_TEMPLATE)
            fallback["regression_areas"] = [
                {"area": module_name, "focus": "General regression testing for this module"}
            ]
            categories[module_name] = {"release_scope_name": module_name, **fallback}

    return categories


def _assign_defects_to_categories(defects_df, categories):
    """Return {category_key: [defect_dict, ...]} for defects matching each category's keywords."""
    assignments = {key: [] for key in categories}

    for _, row in defects_df.iterrows():
        text = f"{row['module']} {row['summary']}".lower()
        defect = {
            "key": row["key"],
            "summary": row["summary"],
            "module": row["module"],
            "severity": row["severity"],
            "priority": row["priority"],
        }
        for category_key, config in categories.items():
            keywords = config["defect_keywords"]
            if keywords and any(kw in text for kw in keywords):
                assignments[category_key].append(defect)

    return assignments


def _category_score(defects):
    return sum(SEVERITY_WEIGHTS.get(d["severity"], SEVERITY_WEIGHTS["Unknown"]) for d in defects)


def _historical_trend(defect_count):
    if defect_count >= 2:
        return f"Recurring ({defect_count} historical defects)"
    if defect_count == 1:
        return "Isolated (1 historical defect)"
    return "No historical defects found"


def compute_top_risk_areas(categories, assignments):
    areas = []
    for category_key, config in categories.items():
        defects = assignments[category_key]
        score = _category_score(defects)
        severity_counts = {"Critical": 0, "Major": 0, "Minor": 0, "Unknown": 0}
        for d in defects:
            severity_counts[d["severity"] if d["severity"] in severity_counts else "Unknown"] += 1

        risk_level = _category_risk_level(score)

        reason_parts = []
        if config["context_risk_level"] != "Unknown":
            reason_parts.append(f"Project context rates this module as '{config['context_risk_level']}' risk")
        if defects:
            reason_parts.append(
                f"{len(defects)} related historical defect(s) "
                f"(Critical: {severity_counts['Critical']}, Major: {severity_counts['Major']}, "
                f"Minor: {severity_counts['Minor']})"
            )
        else:
            reason_parts.append("No related historical defects, but module is in current release scope")

        areas.append({
            "module": config["release_scope_name"],
            "risk_level": risk_level,
            "defect_count": len(defects),
            "historical_trend": _historical_trend(len(defects)),
            "reason": "; ".join(reason_parts) + ".",
            "_score": score,
        })

    areas.sort(key=lambda a: a["_score"], reverse=True)
    for a in areas:
        del a["_score"]
    return areas


def compute_release_risk_score(defects_df, categories, assignments):
    total_defects = len(defects_df)

    in_scope_severity_counts = {"Critical": 0, "Major": 0, "Minor": 0, "Unknown": 0}
    recurring_categories = 0
    for category_key, defects in assignments.items():
        if len(defects) >= 2:
            recurring_categories += 1
        for d in defects:
            severity = d["severity"] if d["severity"] in in_scope_severity_counts else "Unknown"
            in_scope_severity_counts[severity] += 1

    historical_volume_factor = min(1.0, total_defects / 50)

    breakdown = {
        "base_score": SCORE_BASE,
        "historical_defect_volume": {
            "total_historical_defects": total_defects,
            "factor": round(historical_volume_factor, 2),
            "contribution": round(historical_volume_factor * SCORE_HISTORICAL_VOLUME_WEIGHT, 2),
        },
        "critical_defects_in_scope": {
            "count": in_scope_severity_counts["Critical"],
            "contribution": round(in_scope_severity_counts["Critical"] * SCORE_CRITICAL_WEIGHT, 2),
        },
        "major_defects_in_scope": {
            "count": in_scope_severity_counts["Major"],
            "contribution": round(in_scope_severity_counts["Major"] * SCORE_MAJOR_WEIGHT, 2),
        },
        "minor_defects_in_scope": {
            "count": in_scope_severity_counts["Minor"] + in_scope_severity_counts["Unknown"],
            "contribution": round((in_scope_severity_counts["Minor"] + in_scope_severity_counts["Unknown"]) * SCORE_MINOR_WEIGHT, 2),
        },
        "modules_in_release_scope": {
            "count": len(categories),
            "contribution": round(len(categories) * SCORE_MODULE_IN_SCOPE_WEIGHT, 2),
        },
        "recurring_defect_categories": {
            "count": recurring_categories,
            "contribution": round(recurring_categories * SCORE_RECURRENCE_WEIGHT, 2),
        },
    }

    raw_score = (
        SCORE_BASE
        + breakdown["historical_defect_volume"]["contribution"]
        + breakdown["critical_defects_in_scope"]["contribution"]
        + breakdown["major_defects_in_scope"]["contribution"]
        + breakdown["minor_defects_in_scope"]["contribution"]
        + breakdown["modules_in_release_scope"]["contribution"]
        + breakdown["recurring_defect_categories"]["contribution"]
    )

    score = round(min(RISK_SCORE_MAX, max(RISK_SCORE_MIN, raw_score)), 1)
    return score, _release_risk_level(score), breakdown


def compute_potential_failures(categories, assignments):
    failures = []
    confidence_rank = {"High": 0, "Medium": 1, "Low": 2}

    for category_key, config in categories.items():
        defects = assignments[category_key]
        defect_text = [f"{d['module']} {d['summary']}".lower() for d in defects]

        for scenario in config["failure_scenarios"]:
            matches = sum(1 for text in defect_text if any(kw in text for kw in scenario["keywords"]))

            if matches >= 2:
                confidence = "High"
                reason = f"Similar defects occurred {matches} times historically in {config['release_scope_name']}."
            elif matches == 1:
                confidence = "Medium"
                reason = f"A similar defect occurred {matches} time historically in {config['release_scope_name']}."
            else:
                confidence = "Low"
                reason = (
                    f"No historical occurrences yet, but this is a typical failure area for "
                    f"{config['release_scope_name']} per the project risk profile."
                )

            failures.append({
                "failure": scenario["name"],
                "module": config["release_scope_name"],
                "impact": scenario["impact"],
                "confidence": confidence,
                "reason": reason,
            })

    failures.sort(key=lambda f: confidence_rank.get(f["confidence"], 3))
    return failures


def compute_regression_recommendations(top_risk_areas, categories):
    recommendations = []
    for priority, area in enumerate(top_risk_areas, start=1):
        config = categories[_category_key_for_area(categories, area["module"])]
        for reg_area in config["regression_areas"]:
            recommendations.append({
                "priority": priority,
                "module": area["module"],
                "area": reg_area["area"],
                "risk_level": area["risk_level"],
                "why": (
                    f"{area['module']} is ranked priority {priority} for regression "
                    f"({area['historical_trend']}, risk level: {area['risk_level']})."
                ),
                "suggested_focus": reg_area["focus"],
            })
    return recommendations


def _category_key_for_area(categories, release_scope_name):
    for key, config in categories.items():
        if config["release_scope_name"] == release_scope_name:
            return key
    raise KeyError(release_scope_name)


def compute_release_readiness(release_risk_score, risk_level, top_risk_areas):
    high_risk_areas = [a["module"] for a in top_risk_areas if a["risk_level"] in ("Critical", "High")]
    open_concerns = [
        f"Historical recurrence of defects in {a['module']} ({a['historical_trend']})"
        for a in top_risk_areas if a["defect_count"] >= 2
    ]

    if risk_level == "Critical":
        readiness = "NO GO"
    elif risk_level in ("High", "Medium"):
        readiness = "CONDITIONAL GO"
    else:
        readiness = "GO"

    recommended_actions = [
        f"Execute {area['module']} regression suite"
        for area in top_risk_areas
        if area["risk_level"] in ("Critical", "High")
    ]
    if not recommended_actions:
        recommended_actions = [f"Execute {area['module']} regression suite" for area in top_risk_areas[:1]]

    return {
        "release_readiness": readiness,
        "high_risk_areas": high_risk_areas,
        "open_concerns": open_concerns or ["None identified from historical data."],
        "recommended_actions": recommended_actions,
    }


def generate_release_risk_report(csv_path=None, release_scope_path=None):
    """Compute the full Production Risk Intelligence report as a JSON-serialisable dict."""
    defects_df = load_defects(csv_path)
    release_scope_modules = load_release_scope(release_scope_path)
    categories = _resolve_categories(release_scope_modules)
    assignments = _assign_defects_to_categories(defects_df, categories)

    score, risk_level, breakdown = compute_release_risk_score(defects_df, categories, assignments)
    top_risk_areas = compute_top_risk_areas(categories, assignments)
    potential_failures = compute_potential_failures(categories, assignments)
    regression_areas = compute_regression_recommendations(top_risk_areas, categories)
    readiness = compute_release_readiness(score, risk_level, top_risk_areas)

    return {
        "release_risk_score": score,
        "risk_level": risk_level,
        "score_breakdown": breakdown,
        "release_scope": release_scope_modules,
        "top_risk_areas": top_risk_areas,
        "potential_failures": potential_failures,
        "recommended_regression_areas": regression_areas,
        "release_readiness": readiness["release_readiness"],
        "release_readiness_details": readiness,
    }


def format_report_text(report):
    """Render the report dict as the executive-friendly text report."""
    lines = []
    lines.append("PRODUCTION RISK INTELLIGENCE REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Release Scope: {', '.join(report['release_scope']) or 'N/A'}")
    lines.append("")
    lines.append(f"Release Risk Score: {report['release_risk_score']} / 10")
    lines.append(f"Risk Level: {report['risk_level']}")
    lines.append("")

    lines.append("TOP RISK AREAS")
    lines.append("-" * 60)
    for i, area in enumerate(report["top_risk_areas"], start=1):
        lines.append(f"{i}. {area['module']}")
        lines.append(f"   Risk Level     : {area['risk_level']}")
        lines.append(f"   Defect Count   : {area['defect_count']}")
        lines.append(f"   Historical Trend: {area['historical_trend']}")
        lines.append(f"   Reason         : {area['reason']}")
        lines.append("")

    lines.append("POTENTIAL PRODUCTION FAILURES")
    lines.append("-" * 60)
    for i, failure in enumerate(report["potential_failures"], start=1):
        lines.append(f"{i}. {failure['failure']} ({failure['module']})")
        lines.append(f"   Impact     : {failure['impact']}")
        lines.append(f"   Confidence : {failure['confidence']}")
        lines.append(f"   Reason     : {failure['reason']}")
        lines.append("")

    lines.append("RECOMMENDED REGRESSION AREAS")
    lines.append("-" * 60)
    current_priority = None
    for item in report["recommended_regression_areas"]:
        if item["priority"] != current_priority:
            current_priority = item["priority"]
            lines.append(f"Priority {current_priority} ({item['module']}, Risk: {item['risk_level']})")
        lines.append(f"  - {item['area']}: {item['suggested_focus']}")
    lines.append("")

    details = report["release_readiness_details"]
    lines.append("RELEASE READINESS RECOMMENDATION")
    lines.append("-" * 60)
    lines.append(f"Release Readiness: {report['release_readiness']}")
    lines.append("")
    lines.append("High Risk Areas:")
    for area in details["high_risk_areas"]:
        lines.append(f"  - {area}")
    lines.append("")
    lines.append("Open Concerns:")
    for concern in details["open_concerns"]:
        lines.append(f"  - {concern}")
    lines.append("")
    lines.append("Recommended Actions:")
    for i, action in enumerate(details["recommended_actions"], start=1):
        lines.append(f"  {i}. {action}")

    return "\n".join(lines)

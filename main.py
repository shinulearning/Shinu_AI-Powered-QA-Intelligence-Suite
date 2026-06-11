"""QA Bug Triage Crew — entry point."""

import json
import os
import sys

from crewai import Crew, Process
from dotenv import load_dotenv

from agents.qa_agents import bug_analyst, production_risk_agent, root_cause_agent, test_recommender
from agents.qa_tasks import build_release_risk_task, build_tasks
from utils.historical_defects import load_historical_defects
from utils.jira_client import SAMPLE_BUG_REPORT, fetch_jira_ticket
from utils.risk_intelligence import format_report_text, generate_release_risk_report

# Ensure emoji output doesn't crash on Windows consoles using cp1252.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

# How to fetch from the JIRA?
# JIRA API

# Try to fetch from JIRA, fallback to sample if it fails
bug_report = fetch_jira_ticket("SCRUM-5")

# Sample bug report fallback
if bug_report is None:
    bug_report = SAMPLE_BUG_REPORT

print("📌 Bug Report:")
print(bug_report)


historical_defects = load_historical_defects()

triage_task, root_cause_task, test_task, risk_analysis_task = build_tasks(bug_report, historical_defects)

# Production Risk Intelligence: deterministically compute the release-level
# risk report (score, top risk areas, potential failures, regression plan,
# readiness call) from historical defects + release scope + project context.
release_risk_report = generate_release_risk_report()
release_risk_report_text = format_report_text(release_risk_report)
release_risk_task = build_release_risk_task(release_risk_report_text)

crew = Crew(
    agents=[bug_analyst, root_cause_agent, test_recommender, production_risk_agent],
    tasks=[triage_task, root_cause_task, test_task, risk_analysis_task, release_risk_task],
    process=Process.sequential,
    verbose=True
)

print("🔍 QA Bug Triage Crew — Starting Analysis")
print("=" * 60)

result = crew.kickoff()
print("\n" + "=" * 60)
print("📋 FINAL TRIAGE REPORT")
print("=" * 60)
print(result)

print("\n" + "=" * 60)
print("📊 PRODUCTION RISK INTELLIGENCE REPORT")
print("=" * 60)
print(release_risk_report_text)
print("\nExecutive Summary:")
print(release_risk_task.output.raw if release_risk_task.output else "")

# Persist the structured + human-readable risk reports for management review.
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(output_dir, exist_ok=True)

with open(os.path.join(output_dir, "production_risk_report.json"), "w", encoding="utf-8") as f:
    json.dump(release_risk_report, f, indent=2)

with open(os.path.join(output_dir, "production_risk_report.txt"), "w", encoding="utf-8") as f:
    f.write(release_risk_report_text)
    if release_risk_task.output:
        f.write("\n\nExecutive Summary:\n")
        f.write(release_risk_task.output.raw)

print(f"\n📁 Risk reports saved to: {output_dir}")

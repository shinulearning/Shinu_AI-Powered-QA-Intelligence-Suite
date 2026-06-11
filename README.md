AI-Powered QA Intelligence Suite
AI-powered QA Intelligence Suite using CrewAI, Jira Integration, Defect Intelligence, Root Cause Analysis, Production Risk Prediction, and Regression Recommendation.


AI-Powered Defect Analysis and Assignment Assistant

Bug Triage Agent is an intelligent multi-agent system built using CrewAI that automates the initial defect triage process by analyzing bug reports, identifying probable root causes, assessing severity and priority, and recommending the most suitable assignee or team for resolution.

The agent leverages Large Language Models (LLMs), project knowledge bases, historical defect data, application documentation, and test execution results to provide consistent and data-driven triage decisions.

Key Capabilities
1. Automated Bug Analysis
Reads bug descriptions, logs, screenshots, stack traces, and test results.
Extracts critical information from defect reports.
Identifies affected modules and functionalities.
2. Severity and Priority Recommendation
Evaluates business impact and technical impact.
Suggests Severity (Critical, Major, Minor, etc.).
Recommends Priority (P1, P2, P3, etc.).
Reduces subjective decision-making during triage meetings.
3. Root Cause Prediction
Analyzes defect patterns and historical issues.
Predicts likely causes such as:
UI defect
Backend issue
API failure
Configuration issue
Environment issue
Data-related issue
4. Intelligent Assignment Recommendation
Identifies the most relevant developer or team.
Uses module ownership and historical defect resolution data.
Reduces reassignment cycles.
5. Duplicate Defect Detection
Compares new defects against historical defects.
Flags potential duplicates.
Helps reduce defect backlog noise.
6. Risk and Impact Assessment
Identifies affected business areas.
Predicts regression risks.
Suggests impacted test suites.
7. Knowledge Base Integration
Connects with:
Jira
Confluence
Test Management Tools
Historical Defect Repositories
Requirement Documents
8. Triage Summary Generation

Automatically generates:

Bug Summary
------------
Module: Login
Severity: High
Priority: P1
Probable Cause: Token Validation Failure
Recommended Team: Backend Authentication Team
Duplicate Risk: Low
Suggested Action: Immediate Investigation
Proposed Multi-Agent Architecture
Agent	Responsibility
Defect Analyzer Agent	Analyze bug details
Log Analysis Agent	Review logs and stack traces
Root Cause Agent	Predict probable cause
Severity Assessment Agent	Recommend severity
Assignment Agent	Suggest assignee/team
Duplicate Detection Agent	Find similar historical defects
Report Generator Agent	Create triage summary
Business Benefits
Reduces manual triage effort by 50–70%.
Improves consistency in defect classification.
Faster assignment to the right team.
Reduces triage meeting duration.
Enables data-driven defect management.
Accelerates defect resolution lifecycle.
# ShinuAI Crew — QA Bug Triage Agent

Lightweight agent for triaging QA bug reports and assisting automated bug classification.

## Files
- `main.py` — entry point: fetches the bug report, builds the crew, runs the triage, and generates the Production Risk Intelligence report
- `agents/llm.py` — Groq LLM setup (`GroqLLM`, `groq_llm`)
- `agents/qa_agents.py` — agent definitions (Bug Triage Analyst, Root Cause Investigator, Test Recommender, Production Risk Analyst)
- `agents/qa_tasks.py` — task definitions for the crew (`build_tasks`, `build_release_risk_task`)
- `utils/jira_client.py` — JIRA ticket fetching helpers and sample bug report fallback
- `utils/historical_defects.py` — loads and summarizes historical defect data from `resources/historical_defects.csv`
- `utils/risk_intelligence.py` — Production Risk Intelligence engine: computes the Release Risk Score, Top Risk Areas, Potential Production Failures, Recommended Regression Areas, and Release Readiness recommendation from `resources/historical_defects.csv`, `resources/release_scope.txt`, and `resources/project_context.md`
- `resources/historical_defects.csv` — historical defect/bug records (Jira export format) used for risk analysis
- `resources/project_context.md` — module risk profile and production risk rules used to enrich the risk report
- `resources/release_scope.txt` — list of modules included in the current release
- `output/` — generated `production_risk_report.json` and `production_risk_report.txt` (created on each run)
- `requirement.txt` — Python dependencies

## Requirements
- Python 3.8+
- Install dependencies:

```bash
pip install -r requirement.txt
```

## Environment
Create a `.env` file from `.env_Sample` and set the required variables.

```bash
copy .env_Sample .env
# then edit .env and fill values
```

Common variables:
- `OPENAI_API_KEY` — API key for language model access
- `GITHUB_TOKEN` — (optional) token for GitHub API operations

## Usage
Run the main script:

```bash
python main.py
```

## Production Risk Intelligence
In addition to the per-bug triage workflow, every run also produces an
executive-friendly **Production Risk Intelligence report** for the upcoming
release. This is computed deterministically with pandas (no ML models, no
vector DB) from:

- `resources/historical_defects.csv` — historical defects, severities, and modules
- `resources/release_scope.txt` — modules included in the current release
- `resources/project_context.md` — module risk profile and known failure patterns

The report includes:
1. **Release Risk Score** (1.0–10.0) with a transparent, weighted breakdown
2. **Top Risk Areas** — risk level, defect count, historical trend, and reason per module
3. **Potential Production Failures** — likely failure scenarios with impact and confidence level
4. **Recommended Regression Areas** — prioritized regression plan per module
5. **Release Readiness Recommendation** — GO / CONDITIONAL GO / NO GO with supporting reasons

A short executive summary is added by the Production Risk Analyst agent on
top of these computed figures (it does not change the score or readiness
call). On each run, the full report is printed to the console and saved to:

- `output/production_risk_report.json` — structured output
- `output/production_risk_report.txt` — human-readable report

## Contributing
Feel free to open issues or PRs in the repository.

## License
Use as you like. Add a license file if needed.


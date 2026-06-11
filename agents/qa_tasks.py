"""QA Bug Triage Tasks — built around the bug report under analysis."""

from crewai import Task

from agents.qa_agents import bug_analyst, production_risk_agent, root_cause_agent, test_recommender

# Task 1: Classify the bug
# Task 2: Investigate root cause (uses triage output as context)
# Task 3: Recommend tests (uses both previous outputs)
# Task 4: Assess production risk (uses historical defect data)


def build_tasks(bug_report, historical_defects):
    triage_task = Task(
        description=f"""Analyze and classify this bug report:

        {bug_report}

        Provide:
        1. Severity (P0-P4) with justification
        2. Category (UI, Functional, Performance, Security, Data)
        3. Affected component/module
        4. Business impact assessment
        5. Recommended priority for sprint planning""",

        expected_output="""A structured triage report with severity,
        category, component, business impact, and sprint priority.""",
        agent=bug_analyst
    )

    # Task 2: Investigate root cause (uses triage output as context)
    root_cause_task = Task(
        description=f"""Based on the triage analysis, investigate the
    likely root cause of this bug:

    {bug_report}

        Provide:
        1. Most likely root cause
        2. System layer affected (UI/API/Service/DB/Infra)
        3. Related components that might be impacted
        4. Suggested investigation steps
        5. Which logs/dashboards to check first""",

        expected_output="""A root cause analysis report with the probable
    cause, affected layer, related components, and investigation steps.""",
        agent=root_cause_agent,
        context=[triage_task]  # Receives output from triage
    )

    test_task = Task(
        description=f"""Based on the triage and root cause analysis,
    recommend test cases for this bug:

    {bug_report}

        Provide:
        1. Verification test (confirm the fix works)
        2. 1-2 regression test cases
        3. 1-2 Edge cases to add to the test suite
        4. Any 1 load/performance tests if applicable
        You need to create only very Important 2-3 Test cases and which should cover the main scenarios """,

        expected_output="""A test recommendation report with verification
    tests, regression cases, and edge cases.""",
        agent=test_recommender,
        context=[triage_task, root_cause_task]  # Uses both outputs
    )

    # Task 4: Assess production risk (uses historical defect data)
    risk_analysis_task = Task(
        description=f"""Based on the triage and root cause analysis,
    assess the production risk of this bug using the historical defect
    data below:

    {bug_report}

    Historical Defect Data:
    {historical_defects}

        Provide:
        1. Risk Level (Low/Medium/High/Critical) with justification
        2. Similar past defects and any recurrence patterns
        3. Modules/components with a history of related issues
        4. Recommendations to mitigate production risk""",

        expected_output="""A production risk analysis report with a risk
    level, related historical defects, affected modules, and mitigation
    recommendations.""",
        agent=production_risk_agent,
        context=[triage_task, root_cause_task, test_task]  # Uses all prior outputs
    )

    return triage_task, root_cause_task, test_task, risk_analysis_task


def build_release_risk_task(release_risk_report_text):
    """Task: turn the pre-computed Production Risk Intelligence report into an
    executive summary for management. The risk score, top risk areas,
    potential failures, regression plan, and readiness call are all computed
    deterministically beforehand (see utils.risk_intelligence) - this task
    only adds a short narrative on top of those numbers, it must not change them.
    """
    release_risk_task = Task(
        description=f"""Below is a pre-computed Production Risk Intelligence
    report for the upcoming release, generated from historical defect data,
    project context, and release scope:

    {release_risk_report_text}

        Write a short executive summary (4-6 sentences) for QA leadership and
        management based ONLY on the figures and findings above. Do not
        invent new numbers, modules, or defects, and do not change the
        Release Risk Score, Risk Level, or Release Readiness call given above.
        Highlight the overall risk posture, the top risk area(s), the most
        likely production failure(s), and the release readiness
        recommendation with its key reasons.""",

        expected_output="""A concise (4-6 sentence) executive summary
    covering overall risk posture, top risk areas, likely production
    failures, and the release readiness recommendation.""",
        agent=production_risk_agent,
    )

    return release_risk_task

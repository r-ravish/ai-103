import streamlit as st
import pandas as pd
import json
from pathlib import Path

# ============================================================
# Page Configuration
# ============================================================

st.set_page_config(
    page_title="Enterprise Knowledge Agent",
    page_icon="🤖",
    layout="wide"
)

# ============================================================
# Dashboard Title
# ============================================================

st.title("Enterprise Knowledge Agent")
st.write("Dashboard — Live Evaluation & Feedback Data")

st.divider()

# ============================================================
# 1. Evaluation Results
# ============================================================

st.header("Evaluation Results")

evaluation_file = Path("evaluation/results/day3-results.json")
if not evaluation_file.exists():
    evaluation_file = Path(__file__).resolve().parent.parent / "evaluation/results/day3-results.json"

if evaluation_file.exists():

    with open(evaluation_file, "r", encoding="utf-8") as f:
        evaluation_json = json.load(f)

    results = evaluation_json.get("results") or []

    evaluation_rows = []

    for result in results:

        citations = result.get("citations") or []

        citation_source = ", ".join(
            citation.get("source_file", "")
            for citation in citations
            if citation.get("source_file")
        )

        evaluation_rows.append({
            "Question ID": result.get("question_id"),
            "Question": result.get("question"),
            "Category": result.get("category"),
            "Correct": result.get("correct"),
            "Citation Present": result.get("citation_present"),
            "Citation Correct": result.get("citation_correct"),
            "Hallucination": result.get("hallucination_detected"),
            "Status": result.get("pass_fail"),
            "Latency (ms)": result.get("latency_ms"),
            "Citation": citation_source or "None"
        })

    evaluation_df = pd.DataFrame(evaluation_rows)

    # --------------------------------------------------------
    # Summary Metrics
    # --------------------------------------------------------

    total_questions = len(results)

    correct_count = sum(
        result.get("correct") is True
        for result in results
    )

    passed_count = sum(
        result.get("pass_fail") == "PASS"
        for result in results
    )

    failed_count = sum(
        result.get("pass_fail") == "FAIL"
        for result in results
    )

    overall_score = (
        (correct_count / total_questions) * 100
        if total_questions
        else 0
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Overall Score",
            f"{overall_score:.1f}%"
        )

    with col2:
        st.metric(
            "Questions Evaluated",
            total_questions
        )

    with col3:
        st.metric(
            "Passed",
            passed_count
        )

    with col4:
        st.metric(
            "Failed",
            failed_count
        )

    # --------------------------------------------------------
    # Evaluation Details
    # --------------------------------------------------------

    st.subheader("Evaluation Details")

    st.dataframe(
        evaluation_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.warning(
        "Evaluation results are not available yet."
    )

    # Keep results available for the remaining sections
    results = []

st.divider()

# ============================================================
# 2. Knowledge Gaps
# ============================================================

st.header("Knowledge Gaps")

knowledge_gap_results = [
    result
    for result in results
    if result.get("category") == "knowledge_gap"
]

if knowledge_gap_results:

    knowledge_gap_rows = []

    for result in knowledge_gap_results:

        knowledge_gap_rows.append({
            "Question ID": result.get("question_id"),
            "Question": result.get("question"),
            "Expected Behavior": result.get("expected_behavior"),
            "Actual Answer": result.get("answer"),
            "Status": result.get("pass_fail")
        })

    knowledge_gap_df = pd.DataFrame(
        knowledge_gap_rows
    )

    gap_col1, gap_col2 = st.columns(2)

    with gap_col1:
        st.metric(
            "Knowledge Gap Cases",
            len(knowledge_gap_results)
        )

    with gap_col2:

        gap_failed = sum(
            result.get("pass_fail") == "FAIL"
            for result in knowledge_gap_results
        )

        st.metric(
            "Failed Gap Cases",
            gap_failed
        )

    st.subheader("Knowledge Gap Details")

    st.dataframe(
        knowledge_gap_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No knowledge-gap cases found in the evaluation results."
    )

st.divider()

# ============================================================
# 3. Out of Scope
# ============================================================

st.header("Out of Scope")

out_of_scope_results = [
    result
    for result in results
    if result.get("category") == "out_of_scope"
]

if out_of_scope_results:

    out_of_scope_rows = []

    for result in out_of_scope_results:

        out_of_scope_rows.append({
            "Question ID": result.get("question_id"),
            "Question": result.get("question"),
            "Expected Behavior": result.get("expected_behavior"),
            "Actual Answer": result.get("answer"),
            "Status": result.get("pass_fail")
        })

    out_of_scope_df = pd.DataFrame(
        out_of_scope_rows
    )

    st.metric(
        "Out-of-Scope Cases",
        len(out_of_scope_results)
    )

    st.subheader("Out-of-Scope Details")

    st.dataframe(
        out_of_scope_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No out-of-scope cases found in the evaluation results."
    )

st.divider()

# ============================================================
# 4. User Feedback
# ============================================================

st.header("User Feedback")

st.info(
    "Feedback storage is not connected yet. "
    "There is currently no /feedback endpoint available. "
    "Feedback integration will be added when backend storage "
    "is available."
)

st.divider()

# ============================================================
# 5. Escalation / Human Review
# ============================================================

st.header("Escalation / Human Review")

st.info(
    "Escalation fields are defined in the /chat contract, "
    "but the current dashboard does not yet have access to "
    "a persisted escalation history or API."
)

st.subheader("Expected /chat Escalation Fields")

st.code(
    """response_id
escalation_required
escalation_reason
action_taken
action_type
ticket_id""",
    language="text"
)

st.subheader("Escalation Rules")

st.write(
    "Knowledge-gap escalation:"
)

st.code(
    'escalation_required == true AND '
    'escalation_reason == "knowledge_gap"',
    language="text"
)

st.write(
    "Out-of-scope escalation:"
)

st.code(
    'escalation_required == true AND '
    'escalation_reason == "out_of_scope"',
    language="text"
)

st.divider()

# ============================================================
# Dashboard Status
# ============================================================

st.caption(
    "Evaluation results and knowledge-gap cases are loaded "
    "from the project's evaluation output. User feedback and "
    "historical escalation data are not yet available through "
    "a backend endpoint."
)
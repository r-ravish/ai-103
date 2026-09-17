import streamlit as st
import pandas as pd

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
st.write("Dashboard — Mock Evaluation & Feedback Data")

st.divider()

# ============================================================
# 1. Evaluation Results
# ============================================================

st.header("Evaluation Results")

# Mock evaluation data
evaluation_data = [
    {
        "Question": "What is the company's leave policy?",
        "Score": 0.92,
        "Status": "Answered",
        "Grounded": "Yes",
        "Citation": "HR Policy Document"
    },
    {
        "Question": "How can I claim travel reimbursement?",
        "Score": 0.88,
        "Status": "Answered",
        "Grounded": "Yes",
        "Citation": "Travel Policy"
    },
    {
        "Question": "What is the laptop replacement policy?",
        "Score": 0.81,
        "Status": "Answered",
        "Grounded": "Yes",
        "Citation": "IT Asset Policy"
    },
    {
        "Question": "What is the employee bonus structure?",
        "Score": 0.42,
        "Status": "Failed",
        "Grounded": "No",
        "Citation": "No sufficient evidence"
    },
    {
        "Question": "What is the work-from-home allowance?",
        "Score": 0.76,
        "Status": "Answered",
        "Grounded": "Partial",
        "Citation": "Employee Benefits"
    }
]

evaluation_df = pd.DataFrame(evaluation_data)

# Summary metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Overall Score", "82%")

with col2:
    st.metric("Questions Evaluated", "5")

with col3:
    answered_count = len(
        evaluation_df[evaluation_df["Status"] == "Answered"]
    )
    st.metric("Answered", answered_count)

with col4:
    failed_count = len(
        evaluation_df[evaluation_df["Status"] == "Failed"]
    )
    st.metric("Failed", failed_count)

st.subheader("Evaluation Details")

st.dataframe(
    evaluation_df,
    use_container_width=True,
    hide_index=True
)

st.divider()

# ============================================================
# 2. Knowledge Gaps
# ============================================================

st.header("Knowledge Gaps")

knowledge_gap_data = [
    {
        "Question": "What is the employee bonus structure?",
        "Gap Type": "Insufficient Evidence",
        "Priority": "High",
        "Action": "Escalate"
    },
    {
        "Question": "Does the company provide relocation assistance?",
        "Gap Type": "Unanswered",
        "Priority": "Medium",
        "Action": "Review Corpus"
    },
    {
        "Question": "What is the international travel approval process?",
        "Gap Type": "Insufficient Evidence",
        "Priority": "High",
        "Action": "Escalate"
    },
    {
        "Question": "Are employees eligible for internet reimbursement?",
        "Gap Type": "Unanswered",
        "Priority": "Medium",
        "Action": "Add Documentation"
    }
]

knowledge_gap_df = pd.DataFrame(knowledge_gap_data)

gap_col1, gap_col2, gap_col3 = st.columns(3)

with gap_col1:
    st.metric("Total Knowledge Gaps", len(knowledge_gap_df))

with gap_col2:
    high_priority = len(
        knowledge_gap_df[knowledge_gap_df["Priority"] == "High"]
    )
    st.metric("High Priority", high_priority)

with gap_col3:
    escalation_count = len(
        knowledge_gap_df[knowledge_gap_df["Action"] == "Escalate"]
    )
    st.metric("Requires Escalation", escalation_count)

st.subheader("Knowledge Gap Details")

st.dataframe(
    knowledge_gap_df,
    use_container_width=True,
    hide_index=True
)

st.divider()

# ============================================================
# 3. User Feedback
# ============================================================

st.header("User Feedback")

feedback_data = [
    {
        "User": "User 001",
        "Feedback": "The answer was clear and helpful.",
        "Sentiment": "Positive",
        "Rating": 5
    },
    {
        "User": "User 002",
        "Feedback": "The answer included a useful policy citation.",
        "Sentiment": "Positive",
        "Rating": 5
    },
    {
        "User": "User 003",
        "Feedback": "The answer did not contain enough information.",
        "Sentiment": "Negative",
        "Rating": 2
    },
    {
        "User": "User 004",
        "Feedback": "The response was mostly correct but needed more detail.",
        "Sentiment": "Negative",
        "Rating": 3
    },
    {
        "User": "User 005",
        "Feedback": "The response was quick and relevant.",
        "Sentiment": "Positive",
        "Rating": 4
    }
]

feedback_df = pd.DataFrame(feedback_data)

positive_count = len(
    feedback_df[feedback_df["Sentiment"] == "Positive"]
)

negative_count = len(
    feedback_df[feedback_df["Sentiment"] == "Negative"]
)

feedback_col1, feedback_col2, feedback_col3 = st.columns(3)

with feedback_col1:
    st.metric("Total Feedback", len(feedback_df))

with feedback_col2:
    st.metric("Positive Feedback", positive_count)

with feedback_col3:
    st.metric("Negative Feedback", negative_count)

st.subheader("Recent Feedback")

st.dataframe(
    feedback_df,
    use_container_width=True,
    hide_index=True
)

st.divider()

st.caption(
    "Mock/sample data for dashboard development. "
    "This data will be replaced with real evaluation and tracing data later."
)
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Enterprise Knowledge Agent",
    page_icon="🤖",
    layout="wide"
)

# Dashboard title
st.title("Enterprise Knowledge Agent")
st.write("Dashboard Skeleton")

st.divider()

# ============================================================
# 1. Evaluation Results
# ============================================================

st.header("Evaluation Results")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Overall Score", "87%")

with col2:
    st.metric("Questions Evaluated", "120")

with col3:
    st.metric("Successful Answers", "104")

st.write("Mock evaluation data for today's dashboard skeleton.")

st.divider()

# ============================================================
# 2. Knowledge Gaps
# ============================================================

st.header("Knowledge Gaps")

knowledge_gaps = [
    "Company leave policy",
    "Travel reimbursement policy",
    "IT security guidelines",
    "Employee onboarding process"
]

for gap in knowledge_gaps:
    st.write(f"• {gap}")

st.write("These are placeholder knowledge gaps for today's prototype.")

st.divider()

# ============================================================
# 3. User Feedback
# ============================================================

st.header("User Feedback")

feedback_col1, feedback_col2 = st.columns(2)

with feedback_col1:
    st.metric("Positive Feedback", "82%")

with feedback_col2:
    st.metric("Negative Feedback", "18%")

st.write("Mock user feedback data for today's dashboard skeleton.")
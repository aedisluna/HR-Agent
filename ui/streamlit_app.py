import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8001"

STATUSES = [
    "draft",
    "applied",
    "waiting",
    "recruiter_screen",
    "test_task",
    "interview",
    "rejected",
    "offer",
]


def api_get(path: str):
    response = requests.get(f"{API_BASE}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict):
    response = requests.post(f"{API_BASE}{path}", json=payload, timeout=300)
    response.raise_for_status()
    return response.json()


def api_patch(path: str, payload: dict):
    response = requests.patch(f"{API_BASE}{path}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="Job Application Assistant", layout="wide")
st.title("Local Job Application Assistant")
st.caption("LinkedIn Safe Mode: copy job text here, review generated content, apply manually.")

try:
    api_get("/health")
except requests.RequestException:
    st.error("FastAPI is not running. Start it with: `uvicorn app.main:app --reload`")
    st.stop()

tab_analyze, tab_answers, tab_crm = st.tabs(["Analyze Job", "Form Answers", "Applications CRM"])

with tab_analyze:
    col_left, col_right = st.columns(2)

    with col_left:
        company = st.text_input("Company")
        role = st.text_input("Role")
        source = st.text_input("Source", value="linkedin")
        url = st.text_input("Job URL (optional)")
        job_text = st.text_area("Job description", height=320)

        analyze_btn = st.button("Analyze & Generate", type="primary")

    with col_right:
        if analyze_btn:
            if len(job_text.strip()) < 20:
                st.warning("Paste a longer job description.")
            else:
                with st.spinner("Analyzing with local LLM..."):
                    try:
                        data = api_post(
                            "/analyze-and-save",
                            {
                                "job_text": job_text,
                                "company": company or None,
                                "role": role or None,
                                "source": source,
                                "url": url or None,
                                "save_application": True,
                            },
                        )
                        st.session_state["last_analysis"] = data
                    except requests.RequestException as exc:
                        st.error(f"Request failed: {exc}")

        data = st.session_state.get("last_analysis")
        if data:
            analysis = data["analysis"]
            st.metric("Fit Score", analysis.get("fit_score") or "—")
            st.markdown("### Analysis")
            st.markdown(analysis["result"])
            st.markdown("### Cover Letter")
            st.text_area("Cover letter", value=data["cover_letter"], height=220)
            if data.get("application"):
                st.success(f"Saved as application #{data['application']['id']}")

with tab_answers:
    col_left, col_right = st.columns(2)

    with col_left:
        job_text_answers = st.text_area("Job description", height=200, key="answers_job")
        questions_raw = st.text_area(
            "Form questions (one per line)",
            height=200,
            placeholder="Are you willing to relocate?\nWhat is your salary expectation?",
        )
        generate_btn = st.button("Generate Answers")

    with col_right:
        if generate_btn:
            questions = [q.strip() for q in questions_raw.splitlines() if q.strip()]
            if len(job_text_answers.strip()) < 20:
                st.warning("Paste a longer job description.")
            elif not questions:
                st.warning("Add at least one question.")
            else:
                with st.spinner("Generating answers..."):
                    try:
                        result = api_post(
                            "/generate-answers",
                            {"job_text": job_text_answers, "questions": questions},
                        )
                        st.session_state["last_answers"] = result["result"]
                    except requests.RequestException as exc:
                        st.error(f"Request failed: {exc}")

        if st.session_state.get("last_answers"):
            st.markdown(st.session_state["last_answers"])

with tab_crm:
    try:
        applications = api_get("/applications")
    except requests.RequestException as exc:
        st.error(f"Could not load applications: {exc}")
        applications = []

    if not applications:
        st.info("No applications yet. Analyze a job to create the first one.")
    else:
        for app in applications:
            with st.expander(f"#{app['id']} — {app['company']} / {app['role']} ({app['status']})"):
                new_status = st.selectbox(
                    "Status",
                    STATUSES,
                    index=STATUSES.index(app["status"]) if app["status"] in STATUSES else 0,
                    key=f"status_{app['id']}",
                )
                notes = st.text_area("Notes", value=app.get("notes") or "", key=f"notes_{app['id']}")
                if st.button("Update", key=f"update_{app['id']}"):
                    try:
                        api_patch(
                            f"/applications/{app['id']}",
                            {"status": new_status, "notes": notes},
                        )
                        st.success("Updated")
                        st.rerun()
                    except requests.RequestException as exc:
                        st.error(str(exc))

                if app.get("generated_pitch"):
                    st.markdown("**Pitch**")
                    st.write(app["generated_pitch"])
                if app.get("analysis_result"):
                    st.markdown("**Analysis**")
                    st.markdown(app["analysis_result"])

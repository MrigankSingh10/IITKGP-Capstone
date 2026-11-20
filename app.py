import json
import uuid
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

DEFAULT_API_URL = "http://127.0.0.1:8000"
TRACE_PATH = Path("reports/agent_traces.jsonl")

st.set_page_config(page_title="HR Policy Navigator", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header("Session Settings")
    api_url = st.text_input("FastAPI Base URL", value=DEFAULT_API_URL)
    employee_id = st.text_input("Employee ID", value="EMP-001")
    st.caption(f"Session ID: `{st.session_state.session_id[:8]}`")
    if st.button("Reset Session"):
        st.session_state.history = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

tab_chat, tab_traces = st.tabs(["Assistant Chat", "Tracing Dashboard"])

with tab_chat:
    st.title("HR Policy Navigator")

    for item in st.session_state.history:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            if item.get("meta"):
                st.caption(item["meta"])

    user_prompt = st.chat_input("Ask an HR policy, leave, or benefits question...")
    if user_prompt:
        st.session_state.history.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            try:
                resp = requests.post(
                    f"{api_url.rstrip('/')}/chat",
                    json={
                        "session_id": st.session_state.session_id,
                        "employee_id": employee_id or None,
                        "query": user_prompt,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                body = resp.json()
                answer = body.get("answer", "")
                citations = body.get("citations", [])
                route = body.get("route_taken", "unknown")
                latency = body.get("latency_ms", 0.0)

                meta_parts = [f"Route: `{route}`", f"Latency: `{latency} ms`"]
                if citations:
                    meta_parts.append(f"Citations: `{', '.join(citations)}`")
                meta_line = " | ".join(meta_parts)

                st.markdown(answer)
                st.caption(meta_line)
                st.session_state.history.append(
                    {"role": "assistant", "content": answer, "meta": meta_line}
                )
            except requests.RequestException as exc:
                err_msg = f"Failed to reach API at `{api_url}`: {exc}"
                st.error(err_msg)
                st.session_state.history.append({"role": "assistant", "content": err_msg})

with tab_traces:
    st.title("Execution Traces & Cost")
    if not TRACE_PATH.exists():
        st.info(f"No trace file found yet at `{TRACE_PATH}`.")
    else:
        records = []
        for line in TRACE_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        if not records:
            st.info("Trace log is empty.")
        else:
            df = pd.DataFrame(records)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Calls", len(df))
            col2.metric("Avg Latency (ms)", round(float(df["latency_ms"].mean()), 2))
            col3.metric("Total Cost ($)", round(float(df["estimated_cost_usd"].sum()), 6))
            col4.metric("Refusals", int((df["status"] == "refused").sum()))
            st.dataframe(df.iloc[::-1], use_container_width=True)
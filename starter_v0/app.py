from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version
from chat import run_model_tool_loop, write_transcript, trim_history, now_iso, safe_slug

ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
RUNS_DIR = ROOT / "runs"

load_lab_env(ROOT)

st.set_page_config(
    page_title="AI Research Agent — Workspace Canvas & Execution Pipeline",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Inject CSS for Glassmorphism & Cyberpunk Neon Theme
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

/* Main background gradient */
.stApp {
    background: linear-gradient(135deg, #090d16 0%, #0f172a 50%, #111827 100%) !important;
    color: #f8fafc !important;
}

/* Glassmorphic Cards */
.glass-card {
    background: rgba(30, 41, 59, 0.65) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 16px !important;
    padding: 20px !important;
    margin: 12px 0px !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4) !important;
}

.glass-badge {
    background: rgba(56, 189, 248, 0.15);
    border: 1px solid #38bdf8;
    color: #38bdf8;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    display: inline-block;
}

/* Pipeline Node Graph */
.pipeline-container {
    display: flex;
    align-items: center;
    gap: 12px;
    overflow-x: auto;
    padding: 16px;
    background: rgba(15, 23, 42, 0.8);
    border-radius: 16px;
    border: 1px solid rgba(56, 189, 248, 0.2);
    margin-bottom: 20px;
}

.node-item {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #38bdf8;
    border-radius: 12px;
    padding: 12px 18px;
    color: #e2e8f0;
    font-weight: 600;
    font-size: 13px;
    box-shadow: 0 0 15px rgba(56, 189, 248, 0.25);
    white-space: nowrap;
}

.node-item.active {
    background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
    border-color: #38bdf8;
    box-shadow: 0 0 20px rgba(56, 189, 248, 0.6);
}

.node-arrow {
    color: #64748b;
    font-weight: bold;
    font-size: 16px;
}

/* Weather Widget Card */
.weather-card {
    background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
    border-radius: 16px;
    padding: 20px;
    color: white;
    margin: 10px 0;
    box-shadow: 0 10px 25px -5px rgba(2, 132, 199, 0.5);
}
</style>
""", unsafe_allow_html=True)

# Header Section
col_title, col_status = st.columns([3, 1])
with col_title:
    st.markdown("<h1 style='color: #f8fafc; font-weight: 800;'>⚡ Next-Gen AI Agent Workspace</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8; font-size: 15px;'>Real-time Tool Calling, Visual Pipeline Execution Graph & Multi-Model Canvas</p>", unsafe_allow_html=True)

with col_status:
    st.markdown("""
    <div style='text-align: right; padding-top: 10px;'>
        <span class='glass-badge'>● AGENT ENGINE ONLINE</span>
    </div>
    """, unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.header("⚙️ Agent & Model Hub")

provider_name = st.sidebar.selectbox(
    "Select Provider",
    ["groq", "gemini", "openai", "openrouter", "cerebras"],
    index=0,
)

provider_models = {
    "groq": ["llama-3.1-8b-instant", "openai/gpt-oss-20b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"],
    "gemini": ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"],
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "openrouter": ["openai/gpt-oss-20b:free", "openai/gpt-oss-20b", "meta-llama/llama-3.1-8b-instruct", "openai/gpt-4o-mini"],
    "cerebras": ["llama3.1-8b", "llama3.1-70b"],
}

available_models = provider_models.get(provider_name, ["default"])
model_input = st.sidebar.selectbox("Select Model", available_models, index=0)
version_input = st.sidebar.text_input("Artifact Version Label", value="v6")

system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
tools_path = ARTIFACTS_DIR / "tools.yaml"

if system_prompt_path.exists() and tools_path.exists():
    art_ver = build_artifact_version(version_input, system_prompt_path, tools_path)
    st.sidebar.markdown("---")
    st.sidebar.subheader("📦 Artifact Metadata")
    st.sidebar.markdown(f"""
    <div class='glass-card' style='padding: 12px;'>
        <div style='font-size: 13px; color: #38bdf8; font-weight: bold;'>VERSION {art_ver.artifact_version}</div>
        <div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>Prompt Hash: {art_ver.prompt_hash[:12]}...</div>
        <div style='font-size: 11px; color: #94a3b8;'>Tools Hash: {art_ver.tools_hash[:12]}...</div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.error("Missing system_prompt.md or tools.yaml")


def render_pipeline_graph(rounds: list[dict[str, Any]]) -> None:
    """Hiển thị sơ đồ Pipeline Execution Graph dạng Node Flowchart động."""
    if not rounds:
        st.markdown("""
        <div class='pipeline-container'>
            <div class='node-item active'>👤 User Query</div>
            <div class='node-arrow'>➔</div>
            <div class='node-item'>🧠 Direct Answer</div>
        </div>
        """, unsafe_allow_html=True)
        return

    nodes_html = ["<div class='pipeline-container'>", "<div class='node-item'>👤 User Query</div>"]
    for rnd in rounds:
        round_num = rnd.get("round", 1)
        tool_calls = rnd.get("tool_calls", [])
        if tool_calls:
            for call in tool_calls:
                tool_name = call.get("name")
                nodes_html.append("<div class='node-arrow'>➔</div>")
                nodes_html.append(f"<div class='node-item active'>🛠️ Round {round_num}: {tool_name}</div>")
        else:
            nodes_html.append("<div class='node-arrow'>➔</div>")
            nodes_html.append(f"<div class='node-item'>🧠 Round {round_num}: Thinking</div>")

    nodes_html.append("<div class='node-arrow'>➔</div>")
    nodes_html.append("<div class='node-item' style='border-color: #4ade80; color: #4ade80;'>✨ Final Digest</div>")
    nodes_html.append("</div>")
    st.markdown("".join(nodes_html), unsafe_allow_html=True)


def render_visual_trace(rounds: list[dict[str, Any]]) -> None:
    """Hiển thị suy luận & các thẻ widget trực quan."""
    render_pipeline_graph(rounds)

    for rnd in rounds:
        round_num = rnd.get("round", 1)
        st.markdown(f"#### 🔄 Round {round_num} Pipeline Steps")

        assistant_thought = rnd.get("assistant_text")
        if assistant_thought:
            st.markdown("**🧠 Assistant Reasoning / Plan:**")
            st.info(assistant_thought)

        tool_calls = rnd.get("tool_calls", [])
        tool_results = rnd.get("tool_results", [])

        if tool_calls:
            for idx, call in enumerate(tool_calls):
                tool_name = call.get("name")
                args = call.get("args", {})
                matching_res = tool_results[idx].get("result", {}) if idx < len(tool_results) else None

                # Visual Custom Widget for Weather Tool
                if tool_name == "weather" and matching_res and "temperature" in matching_res:
                    loc = matching_res.get("location", args.get("location", "City"))
                    temp = matching_res.get("temperature", "--")
                    wind = matching_res.get("windspeed", "--")
                    unit = matching_res.get("unit", "°C")
                    st.markdown(f"""
                    <div class='weather-card'>
                        <div style='font-size: 14px; text-transform: uppercase; letter-spacing: 1px;'>🌤️ LIVE WEATHER WIDGET — {loc}</div>
                        <div style='font-size: 36px; font-weight: 800; margin: 8px 0;'>{temp} {unit}</div>
                        <div style='font-size: 13px; opacity: 0.9;'>Wind Speed: {wind} km/h</div>
                    </div>
                    """, unsafe_allow_html=True)

                with st.status(f"Tool `{tool_name}` — Query: `{json.dumps(args, ensure_ascii=False)}`", state="complete" if matching_res else "running"):
                    st.json({"tool": tool_name, "args": args, "output": matching_res})


tab1, tab2, tab3 = st.tabs(["💬 Interactive Chat & Pipeline Canvas", "⚡ Side-by-Side Model Comparison", "📂 Run Inspector"])

with tab1:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("💬 Chat & Query Input")
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "history" not in st.session_state:
            st.session_state.history = []
        if "last_result" not in st.session_state:
            st.session_state.last_result = None

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_prompt := st.chat_input("Ask anything (e.g. 'Thời tiết Hà Nội hôm nay', 'Tìm paper AI Agents')..."):
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("🤖 Executing Agent & Calling Tools..."):
                    try:
                        system_prompt = system_prompt_path.read_text(encoding="utf-8")
                        tool_declarations = load_tool_declarations(tools_path)
                        openai_tools = to_openai_tools(tool_declarations)
                        provider = make_provider(provider_name)
                        model_to_use = model_input if model_input.strip() else None

                        input_messages = [
                            {"role": "system", "content": system_prompt},
                            *trim_history(st.session_state.history, window=5),
                            {"role": "user", "content": user_prompt},
                        ]

                        result = run_model_tool_loop(
                            provider=provider,
                            messages=input_messages,
                            tools=openai_tools,
                            model=model_to_use,
                            max_tool_rounds=4,
                        )

                        assistant_text = result.get("assistant_text", "")
                        st.markdown(assistant_text)
                        st.session_state.last_result = result

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": assistant_text,
                            "trace": result["rounds"],
                        })
                        st.session_state.history.append({"role": "user", "content": user_prompt})
                        st.session_state.history.append({"role": "assistant", "content": assistant_text})

                    except Exception as exc:
                        error_msg = f"❌ Provider Error: {type(exc).__name__} - {str(exc)}"
                        st.error(error_msg)

    with col_right:
        st.subheader("🎨 Real-time Execution Canvas & Artifact Preview")
        if st.session_state.last_result:
            render_visual_trace(st.session_state.last_result["rounds"])
            st.markdown("---")
            st.subheader("📄 Generated Content Output")
            st.markdown(st.session_state.last_result.get("assistant_text", ""))
        else:
            st.info("Submit a query in the chat window to view the visual execution pipeline graph and live artifact preview.")

with tab2:
    st.subheader("⚡ Side-by-Side Model Comparison (A/B Testing Matrix)")
    st.caption("Compare 2 different models or providers on the exact same query in real-time.")

    comp_col1, comp_col2 = st.columns(2)
    with comp_col1:
        model_a = st.selectbox("Model A", available_models, index=0, key="mod_a")
    with comp_col2:
        model_b = st.selectbox("Model B", available_models, index=min(1, len(available_models)-1), key="mod_b")

    compare_prompt = st.text_input("Comparison Query Input:", value="Thời tiết Hà Nội hôm nay và quy định công ty về báo cáo.")

    if st.button("🚀 Run Comparison Benchmark"):
        col_res1, col_res2 = st.columns(2)
        system_prompt = system_prompt_path.read_text(encoding="utf-8")
        tool_declarations = load_tool_declarations(tools_path)
        openai_tools = to_openai_tools(tool_declarations)
        provider = make_provider(provider_name)
        input_msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": compare_prompt}]

        with col_res1:
            st.markdown(f"### 🤖 Model A: `{model_a}`")
            with st.spinner("Running Model A..."):
                t0 = datetime.now()
                res_a = run_model_tool_loop(provider=provider, messages=input_msgs, tools=openai_tools, model=model_a, max_tool_rounds=4)
                dt_a = (datetime.now() - t0).total_seconds()
                st.success(f"Execution Time: {dt_a:.2f}s | Status: {res_a['status']}")
                st.markdown(res_a["assistant_text"])
                st.json(res_a["rounds"])

        with col_res2:
            st.markdown(f"### 🤖 Model B: `{model_b}`")
            with st.spinner("Running Model B..."):
                t0 = datetime.now()
                res_b = run_model_tool_loop(provider=provider, messages=input_msgs, tools=openai_tools, model=model_b, max_tool_rounds=4)
                dt_b = (datetime.now() - t0).total_seconds()
                st.success(f"Execution Time: {dt_b:.2f}s | Status: {res_b['status']}")
                st.markdown(res_b["assistant_text"])
                st.json(res_b["rounds"])

with tab3:
    st.subheader("📂 Inspect Evaluation Runs & Transcripts")
    runs_files = list(RUNS_DIR.glob("*.json")) if RUNS_DIR.exists() else []
    if runs_files:
        selected_run = st.selectbox("Select a Run Log JSON to view:", [f.name for f in runs_files])
        if selected_run:
            run_path = RUNS_DIR / selected_run
            run_data = json.loads(run_path.read_text(encoding="utf-8"))
            st.markdown(f"**Run ID:** `{run_data.get('run_id')}` | **Suite:** `{run_data.get('suite')}` | **Accuracy:** `{run_data.get('summary', {}).get('case_accuracy')}`")
            st.json(run_data.get("summary", {}))
            with st.expander("View Full Case Results"):
                st.json(run_data.get("results", []))
    else:
        st.info("No run JSON logs found in runs/ directory yet. Run evaluation scripts to generate logs.")

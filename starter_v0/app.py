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
    page_title="AI Research Agent — Perplexity Canvas",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Inject CSS for Perplexity Light Glassmorphism Theme
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

/* Main background light gradient */
.stApp {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #e2e8f0 100%) !important;
    color: #0f172a !important;
}

/* Glassmorphic Light Cards */
.glass-card {
    background: rgba(255, 255, 255, 0.95) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(226, 232, 240, 0.9) !important;
    border-radius: 14px !important;
    padding: 14px !important;
    margin: 8px 0px !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03) !important;
}

.glass-badge {
    background: rgba(37, 99, 235, 0.1);
    border: 1px solid #2563eb;
    color: #2563eb;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    display: inline-block;
}

/* Pipeline Node Graph - Light Theme */
.pipeline-container {
    display: flex;
    align-items: center;
    gap: 12px;
    overflow-x: auto;
    padding: 14px;
    background: #ffffff;
    border-radius: 14px;
    border: 1px solid #e2e8f0;
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
}

.node-item {
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 10px 16px;
    color: #334155;
    font-weight: 600;
    font-size: 13px;
    white-space: nowrap;
}

.node-item.active {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    border-color: #2563eb;
    color: #ffffff;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
}

.node-arrow {
    color: #94a3b8;
    font-weight: bold;
    font-size: 16px;
}

/* Weather Widget Card */
.weather-card {
    background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
    border-radius: 14px;
    padding: 18px;
    color: white;
    margin: 10px 0;
    box-shadow: 0 10px 20px -5px rgba(2, 132, 199, 0.3);
}

/* Perplexity Step Expander Styling */
div[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02) !important;
    margin-bottom: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# Header Section
col_title, col_status = st.columns([3, 1])
with col_title:
    st.markdown("<h1 style='color: #0f172a; font-weight: 800;'>⚡ Next-Gen AI Agent Workspace</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #475569; font-size: 15px;'>Perplexity-style Live Tool Canvas & Multi-Model Execution Trace</p>", unsafe_allow_html=True)

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
    "openrouter": ["inclusionai/ling-3.0-flash:free", "openai/gpt-oss-20b:free", "openai/gpt-oss-20b", "meta-llama/llama-3.1-8b-instruct", "openai/gpt-4o-mini"],
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
        <div style='font-size: 13px; color: #2563eb; font-weight: bold;'>VERSION {art_ver.artifact_version}</div>
        <div style='font-size: 11px; color: #64748b; margin-top: 4px;'>Prompt Hash: {art_ver.prompt_hash[:12]}...</div>
        <div style='font-size: 11px; color: #64748b;'>Tools Hash: {art_ver.tools_hash[:12]}...</div>
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
    nodes_html.append("<div class='node-item' style='border-color: #16a34a; color: #16a34a;'>✨ Final Digest</div>")
    nodes_html.append("</div>")
    st.markdown("".join(nodes_html), unsafe_allow_html=True)


def render_perplexity_style_trace(rounds: list[dict[str, Any]]) -> None:
    """Render Perplexity AI style sources & expandable Completed N steps component."""
    if not rounds:
        return

    all_calls = []
    all_results = []
    for rnd in rounds:
        for call in rnd.get("tool_calls", []):
            all_calls.append(call)
        for res in rnd.get("tool_results", []):
            all_results.append(res)

    total_steps = len(all_calls)

    # 1. Render Sources Grid (Perplexity style source cards at top)
    sources = []
    for res_item in all_results:
        res = res_item.get("result", {})
        if isinstance(res, dict):
            if "items" in res and isinstance(res["items"], list):
                for item in res["items"][:4]:
                    if isinstance(item, dict):
                        sources.append({
                            "title": item.get("title") or item.get("topic") or item.get("author") or "Web Article",
                            "url": item.get("url") or item.get("link") or "#",
                            "snippet": item.get("snippet") or item.get("text") or item.get("summary") or "",
                            "domain": item.get("domain") or "web"
                        })
            elif "location" in res:
                sources.append({
                    "title": f"Live Weather: {res.get('location')}",
                    "url": "#",
                    "snippet": f"{res.get('temperature')}°C - Wind: {res.get('windspeed')} km/h",
                    "domain": "open-meteo.com"
                })

    if sources:
        st.markdown("<div style='font-size: 12px; font-weight: 700; color: #64748b; margin-bottom: 6px; letter-spacing: 0.5px;'>SOURCES & REFERENCES</div>", unsafe_allow_html=True)
        cols = st.columns(min(len(sources), 3))
        for idx, src in enumerate(sources[:3]):
            with cols[idx % 3]:
                st.markdown(f"""
                <div class='glass-card' style='padding: 10px 14px;'>
                    <div style='font-size: 11px; color: #2563eb; font-weight: 700;'>🌐 {src['domain']}</div>
                    <div style='font-size: 13px; font-weight: 700; color: #0f172a; margin: 2px 0; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical;'>
                        <a href="{src['url']}" target="_blank" style="color: inherit; text-decoration: none;">{src['title']}</a>
                    </div>
                    <div style='font-size: 11px; color: #64748b; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;'>{src['snippet']}</div>
                </div>
                """, unsafe_allow_html=True)

    # 2. Render Collapsible "Completed X steps >" expander (Perplexity UI)
    step_label = f"Completed {total_steps} step{'s' if total_steps != 1 else ''} ›" if total_steps > 0 else "Completed 1 step ›"
    
    with st.expander(step_label, expanded=False):
        for rnd in rounds:
            round_num = rnd.get("round", 1)
            tool_calls = rnd.get("tool_calls", [])
            tool_results = rnd.get("tool_results", [])
            
            for idx, call in enumerate(tool_calls):
                tool_name = call.get("name")
                args = call.get("args", {})
                res = tool_results[idx].get("result", {}) if idx < len(tool_results) else {}

                icon = "🌐"
                label = "Searching the web"
                if tool_name in ["papers", "paper_text"]:
                    icon = "📚"
                    label = "Researching arXiv papers"
                elif tool_name == "weather":
                    icon = "🌤️"
                    label = "Fetching weather forecast"
                elif tool_name == "policy":
                    icon = "🔒"
                    label = "Checking company policy RAG"
                elif tool_name in ["timeline", "social_search"]:
                    icon = "🐦"
                    label = "Searching Twitter / X posts"
                elif tool_name == "clarify":
                    icon = "💬"
                    label = "Requesting user clarification"

                st.markdown(f"**{icon} {label}**")
                query_val = args.get("query") or args.get("location") or args.get("topic") or args.get("policy_area") or json.dumps(args, ensure_ascii=False)
                st.markdown(f"- 🔍 `Query:` *{query_val}*")
                
                if isinstance(res, dict) and "items" in res and isinstance(res["items"], list):
                    for sub_item in res["items"][:3]:
                        if isinstance(sub_item, dict):
                            item_title = sub_item.get("title") or sub_item.get("author") or "Item"
                            item_domain = sub_item.get("domain") or sub_item.get("url") or ""
                            st.markdown(f"  - 📄 `{item_title}` *( {item_domain} )*")


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
                if "trace" in msg:
                    render_perplexity_style_trace(msg["trace"])
                st.markdown(msg["content"])

        if user_prompt := st.chat_input("Ask anything (e.g. 'Thời tiết Hà Nội hôm nay', 'Tìm paper Attention Is All You Need')..."):
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("🤖 Searching & Reasoning..."):
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
                        
                        # Render Perplexity AI style trace right above the answer!
                        render_perplexity_style_trace(result["rounds"])
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
            render_pipeline_graph(st.session_state.last_result["rounds"])
            render_perplexity_style_trace(st.session_state.last_result["rounds"])
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
                render_perplexity_style_trace(res_a["rounds"])
                st.markdown(res_a["assistant_text"])

        with col_res2:
            st.markdown(f"### 🤖 Model B: `{model_b}`")
            with st.spinner("Running Model B..."):
                t0 = datetime.now()
                res_b = run_model_tool_loop(provider=provider, messages=input_msgs, tools=openai_tools, model=model_b, max_tool_rounds=4)
                dt_b = (datetime.now() - t0).total_seconds()
                st.success(f"Execution Time: {dt_b:.2f}s | Status: {res_b['status']}")
                render_perplexity_style_trace(res_b["rounds"])
                st.markdown(res_b["assistant_text"])

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

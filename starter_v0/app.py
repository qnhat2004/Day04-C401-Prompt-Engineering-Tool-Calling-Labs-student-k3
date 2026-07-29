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
    page_title="AI Research Agent — Showdown & Trace UI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🤖 AI Research Agent — Tool Trace & Reasoning UI")
st.caption("Day 04 Lab — Interactive Tool Calling, Visual Audit Logs & Run Inspector")

# Sidebar Configuration
st.sidebar.header("⚙️ Agent & Model Configuration")

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
    st.sidebar.code(f"Version: {art_ver.artifact_version}\nPrompt Hash: {art_ver.prompt_hash[:12]}...\nTools Hash: {art_ver.tools_hash[:12]}...")
else:
    st.sidebar.error("Missing system_prompt.md or tools.yaml")


def render_human_friendly_trace(rounds: list[dict[str, Any]]) -> None:
    """Hiển thị suy luận và tool trace dưới dạng giao diện trực quan, dễ đọc cho con người."""
    if not rounds:
        st.info("Không có Tool call nào được thực thi (Câu hỏi trả lời trực tiếp).")
        return

    for rnd in rounds:
        round_num = rnd.get("round", 1)
        st.markdown(f"#### 🔄 Round {round_num}")
        
        # 1. Suy luận của Assistant (nếu có)
        assistant_thought = rnd.get("assistant_text")
        if assistant_thought:
            st.markdown("**🧠 Quyết định của AI (Reasoning):**")
            st.info(assistant_thought)

        # 2. Danh sách các Tools được gọi
        tool_calls = rnd.get("tool_calls", [])
        tool_results = rnd.get("tool_results", [])
        
        if tool_calls:
            st.markdown(f"**🛠️ Tool(s) được kích hoạt ({len(tool_calls)} call):**")
            for idx, call in enumerate(tool_calls):
                tool_name = call.get("name")
                args = call.get("args", {})
                
                # Tìm kết quả tương ứng với tool call
                matching_res = None
                if idx < len(tool_results):
                    matching_res = tool_results[idx].get("result", {})

                with st.status(f"Tool `{tool_name}` — Tham số: `{json.dumps(args, ensure_ascii=False)}`", state="complete" if matching_res else "running"):
                    st.markdown(f"**Tên Tool:** `{tool_name}`")
                    st.markdown("**Tham số Truy vấn (Arguments):**")
                    st.json(args)
                    
                    if matching_res:
                        st.markdown("**Kết quả thu thập được (Output):**")
                        # Kiểm tra xem có lỗi không
                        if "error" in matching_res:
                            st.error(f"Lỗi: {matching_res['error']} - {matching_res.get('message', '')}")
                        elif "items" in matching_res and isinstance(matching_res["items"], list):
                            st.success(f"Thu thập thành công {len(matching_res['items'])} dữ liệu/tin tức!")
                            st.json(matching_res["items"])
                        else:
                            st.json(matching_res)


tab1, tab2 = st.tabs(["💬 Interactive Chat & Live Trace", "📊 Saved Runs & Transcripts Inspector"])

with tab1:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "history" not in st.session_state:
        st.session_state.history = []

    # Display existing chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "trace" in msg:
                with st.expander("🔍 Xem Quá Trình Suy Luận & Tool Event Trực Quan"):
                    render_human_friendly_trace(msg["trace"])

    if user_prompt := st.chat_input("Enter your request (e.g. 'Thời tiết Hà Nội hôm nay', 'Tìm paper AI')..."):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("🤖 Agent đang suy luận và truy vấn các Tool..."):
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

                    # Trực quan hóa suy luận & tool call trực quan
                    with st.expander("🔍 Xem Quá Trình Suy Luận & Tool Event Trực Quan", expanded=True):
                        render_human_friendly_trace(result["rounds"])

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

with tab2:
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

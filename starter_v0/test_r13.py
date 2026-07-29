import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
import chat
from run_eval import evaluate_phase_b

# Mock execute_tool_call to execute instantly
chat.execute_tool_call = lambda call: {"tool": call.name, "result": {"items": []}}

system_prompt = Path('artifacts/system_prompt.md').read_text(encoding='utf-8')
openai_tools = to_openai_tools(load_tool_declarations(Path('artifacts/tools.yaml')))
provider = make_provider('groq')

cases = json.loads(Path('data/eval_base.json').read_text(encoding='utf-8'))['cases']
r13_case = [c for c in cases if c['id'] == 'R13_parallel_web_and_tweets'][0]

query = r13_case.get('query') or r13_case.get('input')
print("Query:", query)

input_messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": query}
]

res = chat.run_model_tool_loop(
    provider=provider,
    messages=input_messages,
    tools=openai_tools,
    model='llama-3.1-8b-instant',
    max_tool_rounds=4
)

tool_calls = res['rounds'][0]['tool_calls'] if res['rounds'] else []
eval_res = evaluate_phase_b(r13_case, tool_calls, res.get('assistant_text'))

print("\n--- EVAL RESULT FOR R13 ---")
print("PASSED:", eval_res['passed'])
print("ROUTING CORRECT:", eval_res['routing_correct'])
print("ARGS CORRECT:", eval_res['args_correct'])
print("ACTUAL TOOL CALLS:")
print(json.dumps(eval_res['actual_tool_calls'], ensure_ascii=False, indent=2))

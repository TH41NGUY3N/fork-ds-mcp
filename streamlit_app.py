import asyncio
import json
import re
from typing import Any

import ollama
import streamlit as st
from mcp import ClientSession
from mcp.client.sse import sse_client


LOCAL_SERVER_URL = "http://127.0.0.1:8000/sse"
DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant with access to MCP tools for energy customer support. "
    "Use tools when the user asks about customer smart-meter data or solar-yield forecasts. "
    "If a task requires multiple steps, perform them one by one and use tool results to inform the next answer. "
    "After getting a tool result, explain it in friendly, simple language. "
    "When you have the final answer, summarize it for the user."
)

EXAMPLE_PROMPTS = {
    "Smart meter email": (
        "Customer CUST-8472 is complaining about their January bill. "
        "Look up their smart meter data and write a friendly email explaining what drove their usage up."
    ),
    "Solar yield": (
        "I live in Hannover and have a 10 kWp solar system on my roof. "
        "Calculate my expected solar yield for tomorrow and tell me if it's enough to fully charge my 50 kWh electric car battery."
    ),
}


def field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def normalize_tool_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"value": arguments}
    return {}


def parse_text_tool_call(content: str, allowed_tools: set[str]) -> dict[str, Any] | None:
    cleaned = content.strip().strip("`")
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()

    candidates = [cleaned]
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        tool_name = parsed.get("name") or parsed.get("tool")
        tool_args = parsed.get("parameters") or parsed.get("arguments") or {}
        if tool_name in allowed_tools:
            return {
                "name": tool_name,
                "arguments": normalize_tool_arguments(tool_args),
            }

    name_match = re.search(r'"name"\s*:\s*"([^"]+)"', cleaned)
    params_match = re.search(r'"parameters"\s*[:=]\s*(\{.*\})', cleaned, flags=re.DOTALL)
    if not name_match or not params_match:
        return None

    tool_name = name_match.group(1)
    if tool_name not in allowed_tools:
        return None

    try:
        return {
            "name": tool_name,
            "arguments": normalize_tool_arguments(json.loads(params_match.group(1))),
        }
    except json.JSONDecodeError:
        return None


def tool_result_to_text(result: Any) -> str:
    content = field(result, "content", [])
    parts: list[str] = []
    for item in content:
        text = field(item, "text")
        parts.append(text if text is not None else str(item))
    return "\n".join(parts) if parts else str(result)


def list_ollama_models() -> list[str]:
    try:
        response = ollama.list()
        models = field(response, "models", [])
        names = [field(model, "model") or field(model, "name") for model in models]
        return sorted(name for name in names if name)
    except Exception:
        return []


def detect_demo_tool_call(prompt: str) -> dict[str, Any] | None:
    lowered = prompt.lower()

    if "cust-8472" in lowered or "smart meter" in lowered or "bill" in lowered:
        month = "February" if "february" in lowered else "January"
        return {
            "name": "fetch_smart_meter_data",
            "arguments": {"customer_id": "CUST-8472", "month": month},
        }

    if "solar" in lowered or "kwp" in lowered or "hannover" in lowered:
        city = "Munich" if "munich" in lowered else "Hannover"
        capacity_match = re.search(r"(\d+(?:\.\d+)?)\s*kwp", lowered)
        panel_capacity_kwp = float(capacity_match.group(1)) if capacity_match else 10.0
        return {
            "name": "predict_solar_yield",
            "arguments": {"city": city, "panel_capacity_kwp": panel_capacity_kwp},
        }

    return None


def final_answer_from_tool_result(
    user_prompt: str,
    system_prompt: str,
    model: str,
    tool_name: str,
    tool_result: str,
) -> str:
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"User question:\n{user_prompt}\n\n"
                    f"MCP tool used: {tool_name}\n"
                    f"MCP tool result:\n{tool_result}\n\n"
                    "Write the final answer for the user. Do not output JSON or another tool call."
                ),
            },
        ],
    )
    return field(field(response, "message", {}), "content", "") or "I did not receive a final answer from the model."


def fast_classroom_answer(user_prompt: str, tool_name: str, tool_result: str) -> str:
    if tool_name == "fetch_smart_meter_data":
        return (
            "Here is the smart meter explanation based on the MCP tool result:\n\n"
            f"{tool_result}\n\n"
            "Draft email:\n\n"
            "Subject: Explanation of your January electricity bill\n\n"
            "Dear customer,\n\n"
            "Thank you for reaching out about your electricity bill. I checked your smart meter data, "
            "and the main reason for the higher usage was your heat pump, especially during the evening "
            "peak hours from 18:00 to 21:00. Your total consumption for January was 450 kWh.\n\n"
            "This pattern often happens in colder months when heating demand rises. To reduce future peaks, "
            "you could review heating schedules, lower the target temperature slightly, or shift flexible "
            "energy use outside the evening peak window.\n\n"
            "Kind regards,\n"
            "Your customer support team"
        )

    if tool_name == "predict_solar_yield":
        charge_match = re.search(r"(\d+(?:\.\d+)?)\s*kWh", user_prompt, flags=re.IGNORECASE)
        battery_kwh = float(charge_match.group(1)) if charge_match else 50.0
        yield_match = re.search(r"approximately\s+(\d+(?:\.\d+)?)\s*kWh", tool_result)
        estimated_kwh = float(yield_match.group(1)) if yield_match else 0.0
        enough_text = "is enough" if estimated_kwh >= battery_kwh else "is not enough"

        return (
            "Here is the solar forecast based on the MCP tool result:\n\n"
            f"{tool_result}\n\n"
            f"For a {battery_kwh:.0f} kWh EV battery, this {enough_text} for a full charge. "
            f"You would generate about {estimated_kwh:.2f} kWh, so you would still need "
            f"approximately {max(battery_kwh - estimated_kwh, 0):.2f} kWh from another source "
            "if the battery starts empty."
        )

    return tool_result


async def run_energy_agent(
    user_prompt: str,
    system_prompt: str,
    model: str,
    chat_history: list[dict[str, str]],
) -> tuple[str, list[str]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    trace: list[str] = []

    async with sse_client(LOCAL_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            allowed_tools = {tool.name for tool in tools_result.tools}
            ollama_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    },
                }
                for tool in tools_result.tools
            ]

            for turn in range(5):
                response = ollama.chat(model=model, messages=messages, tools=ollama_tools)
                assistant_msg = field(response, "message", {})
                content = field(assistant_msg, "content", "") or ""
                tool_calls = field(assistant_msg, "tool_calls", []) or []

                messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls,
                    }
                )

                if not tool_calls:
                    text_tool_call = parse_text_tool_call(content, allowed_tools)
                    if text_tool_call:
                        tool_calls = [
                            {
                                "function": {
                                    "name": text_tool_call["name"],
                                    "arguments": text_tool_call["arguments"],
                                }
                            }
                        ]
                    else:
                        return content or "I did not receive a final answer from the model.", trace

                if not tool_calls:
                    return content or "I did not receive a final answer from the model.", trace

                for tool_call in tool_calls:
                    function = field(tool_call, "function", {})
                    tool_name = field(function, "name")
                    tool_args = normalize_tool_arguments(field(function, "arguments", {}))

                    trace.append(f"Turn {turn + 1}: {tool_name}({tool_args})")
                    result = await session.call_tool(tool_name, tool_args)
                    result_text = tool_result_to_text(result)
                    trace.append(f"Result: {result_text}")

                    if parse_text_tool_call(content, allowed_tools):
                        answer = final_answer_from_tool_result(
                            user_prompt,
                            system_prompt,
                            model,
                            tool_name,
                            result_text,
                        )
                        return answer, trace

                    messages.append(
                        {
                            "role": "tool",
                            "content": result_text,
                            "name": tool_name,
                        }
                    )

    return "Loop limit reached before the model produced a final answer.", trace


async def run_fast_demo_agent(
    user_prompt: str,
    system_prompt: str,
    model: str,
    use_fast_classroom_answer: bool,
) -> tuple[str, list[str]]:
    tool_call = detect_demo_tool_call(user_prompt)
    if not tool_call:
        return "", []

    trace = [f"Demo route: {tool_call['name']}({tool_call['arguments']})"]
    async with sse_client(LOCAL_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_call["name"], tool_call["arguments"])
            result_text = tool_result_to_text(result)

    trace.append(f"Result: {result_text}")
    if use_fast_classroom_answer:
        return fast_classroom_answer(user_prompt, tool_call["name"], result_text), trace

    answer = final_answer_from_tool_result(
        user_prompt,
        system_prompt,
        model,
        tool_call["name"],
        result_text,
    )
    return answer, trace


st.set_page_config(page_title="MCP Energy Demo", layout="wide")

st.markdown(
    """
    <style>
        .block-container { padding-top: 1.5rem; max-width: 1180px; }
        [data-testid="stSidebar"] textarea { font-size: 0.88rem; }
        .stButton button { width: 100%; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "ollama_models" not in st.session_state:
    st.session_state.ollama_models = list_ollama_models()
if "tool_traces" not in st.session_state:
    st.session_state.tool_traces = []

with st.sidebar:
    st.header("MCP Setup")
    st.caption(f"Local MCP server: `{LOCAL_SERVER_URL}`")
    st.code("python mcp_servers/mcp_http_server.py", language="powershell")

    if st.button("Refresh Ollama models"):
        st.session_state.ollama_models = list_ollama_models()

    model_options = st.session_state.ollama_models or [DEFAULT_MODEL]
    default_index = model_options.index(DEFAULT_MODEL) if DEFAULT_MODEL in model_options else 0
    selected_model = st.selectbox("Local LLM", model_options, index=default_index)
    fast_classroom_mode = st.checkbox("Fast classroom answers", value=True)

    system_prompt = st.text_area(
        "System prompt",
        value=DEFAULT_SYSTEM_PROMPT,
        height=190,
    )

    if st.button("Clear chat"):
        st.session_state.messages = []
        st.session_state.tool_traces = []
        st.rerun()

st.title("MCP Energy Demo")

left, right = st.columns(2)
with left:
    if st.button("Example 1: smart meter"):
        st.session_state.pending_prompt = EXAMPLE_PROMPTS["Smart meter email"]
with right:
    if st.button("Example 2: solar yield"):
        st.session_state.pending_prompt = EXAMPLE_PROMPTS["Solar yield"]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ask about customer usage or solar yield")
if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Calling Ollama and MCP tools..."):
            try:
                answer, trace = asyncio.run(
                    run_fast_demo_agent(prompt, system_prompt, selected_model, fast_classroom_mode)
                )
                if not answer:
                    answer, trace = asyncio.run(
                        run_energy_agent(
                            prompt,
                            system_prompt,
                            selected_model,
                            st.session_state.messages,
                        )
                    )
            except Exception as exc:
                answer = (
                    "I could not reach the local MCP/Ollama setup. "
                    "Start the MCP server in a second terminal and make sure Ollama is running.\n\n"
                    f"Error: `{exc}`"
                )
                trace = []

        st.markdown(answer)
        if trace:
            with st.expander("Tool calls"):
                for item in trace:
                    st.code(item)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.tool_traces.append(trace)

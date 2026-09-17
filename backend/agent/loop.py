import importlib
import json
import os
import time
from datetime import date
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

AGENT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = AGENT_DIR / "skills"

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Gemini's own 503s ("service unavailable") are usually a brief blip on
# Google's side, per their own error message - worth a couple of extra
# retries beyond whatever the SDK already does internally before we give up
# and surface it to the user.
_TRANSIENT_RETRY_DELAYS_SECONDS = [3, 8, 15]


def _generate_content_with_retry(**kwargs):
    last_exc = None
    for attempt, delay in enumerate([0, *_TRANSIENT_RETRY_DELAYS_SECONDS]):
        if delay:
            time.sleep(delay)
        try:
            return client.models.generate_content(**kwargs)
        except genai_errors.ServerError as exc:
            last_exc = exc
    raise last_exc


def load_agent_config() -> dict:
    with open(AGENT_DIR / "agent.json") as f:
        return json.load(f)


def load_skills(config: dict) -> dict:
    skills = {}
    for skill_name in config["skills"]:
        with open(SKILLS_DIR / f"{skill_name}.json") as f:
            skills[skill_name] = json.load(f)
    return skills


def build_tools_param(skills: dict) -> list:
    declarations = [
        types.FunctionDeclaration(
            name=skill["name"],
            description=skill["description"],
            parameters_json_schema=skill["input_schema"],
        )
        for skill in skills.values()
    ]
    return [types.Tool(function_declarations=declarations)]


def dispatch_tool(skills: dict, name: str, tool_input: dict):
    impl = skills[name]["implementation"]
    module = importlib.import_module(impl["module"])
    func = getattr(module, impl["function"])
    return func(**tool_input)


def _content_to_dict(content) -> dict:
    if hasattr(content, "model_dump"):
        return content.model_dump(mode="json", exclude_none=True)
    return content


def _final_text(last_content: dict) -> str:
    if last_content.get("role") != "model":
        return ""
    parts = last_content.get("parts") or []
    return "\n".join(p["text"] for p in parts if p.get("text"))


def _run_loop(contents: list, config: dict, skills: dict) -> list:
    tools = build_tools_param(skills)
    max_iterations = config.get("loop", {}).get("max_iterations", 12)
    model_name = os.getenv("GEMINI_MODEL", config["model"])
    gen_config = types.GenerateContentConfig(
        system_instruction=config["system_prompt"],
        tools=tools,
    )

    for _ in range(max_iterations):
        response = _generate_content_with_retry(
            model=model_name,
            contents=contents,
            config=gen_config,
        )
        candidate = response.candidates[0]
        contents.append(_content_to_dict(candidate.content))

        parts = candidate.content.parts or []
        function_call_parts = [p for p in parts if getattr(p, "function_call", None)]
        if not function_call_parts:
            break

        response_parts = []
        for part in function_call_parts:
            fc = part.function_call
            try:
                result = dispatch_tool(skills, fc.name, dict(fc.args or {}))
            except Exception as exc:
                result = {"error": str(exc)}
            response_parts.append(
                types.Part.from_function_response(name=fc.name, response=result)
            )
        tool_content = types.Content(role="user", parts=response_parts)
        contents.append(_content_to_dict(tool_content))

    return contents


def _with_today(text: str) -> str:
    return f"Today's date is {date.today().isoformat()}. {text}"


def run_kickoff(user_message: str) -> tuple[list, str]:
    config = load_agent_config()
    skills = load_skills(config)
    contents = [{"role": "user", "parts": [{"text": _with_today(user_message)}]}]
    contents = _run_loop(contents, config, skills)
    return contents, _final_text(contents[-1])


def run_resume(contents: list, injected_message: str) -> tuple[list, str]:
    config = load_agent_config()
    skills = load_skills(config)
    contents = contents + [{"role": "user", "parts": [{"text": _with_today(injected_message)}]}]
    contents = _run_loop(contents, config, skills)
    return contents, _final_text(contents[-1])

"""Bounded ReAct agent loop: JSON-action protocol, cap <= 8 iterations / ~16k tokens (FR-006, Art. IV)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import structlog

from app.infra.llm import BaseLLM, Tier
from app.services.agent.tools.registry import dispatch

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (Path(__file__).parent.parent.parent.parent / "prompts" / "agent_system.txt").read_text()

# Very rough token estimator: 1 token ≈ 4 chars
_CHARS_PER_TOKEN = 4


def _count_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract the first balanced JSON object from LLM output.

    Uses brace-counting (string-aware) so arbitrarily nested objects — e.g.
    {"final": "...", "citations": [{...}, {...}]} — are parsed whole, rather than
    a naive regex grabbing the first inner object.
    """
    text = text.strip()
    # Strip markdown code fences the model often wraps JSON in.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        pass
                    break
        start = text.find("{", start + 1)
    return None


def _strip_json_objects(text: str) -> str:
    """Remove balanced {...} JSON objects from text, leaving any prose behind."""
    out: list[str] = []
    depth = 0
    in_str = False
    esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"' and depth > 0:
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
            continue
        if depth == 0 and ch not in "{}":
            out.append(ch)
    # Drop leftover code-fence markers.
    return "".join(out).replace("```json", "").replace("```", "").strip()


class AgentResult:
    __slots__ = ("answer", "citations", "bounded", "iterations")

    def __init__(self, answer: str, citations: list[dict], *, bounded: bool, iterations: int) -> None:
        self.answer = answer
        self.citations = citations
        self.bounded = bounded
        self.iterations = iterations


async def run_agent(
    user_message: str,
    *,
    llm: BaseLLM,
    context: list[dict[str, str]],
    max_iterations: int = 8,
    token_budget: int = 16000,
) -> AgentResult:
    """Run the bounded ReAct loop and return an AgentResult."""
    messages: list[str] = []
    for turn in context[-10:]:  # last 10 turns for context
        messages.append(f"{turn['role'].capitalize()}: {turn['content']}")

    conversation = "\n".join(messages)
    if conversation:
        conversation = f"\n\nConversation so far:\n{conversation}"

    prompt = f"{_SYSTEM_PROMPT}{conversation}\n\nUser: {user_message}\n\nAssistant:"
    token_used = _count_tokens(prompt)

    citations: list[dict] = []
    iterations = 0

    for iteration in range(max_iterations):
        iterations = iteration + 1

        if token_used >= token_budget:
            log.warning("agent.token_budget_hit", used=token_used, budget=token_budget)
            break

        with structlog.contextvars.bound_contextvars(agent_iteration=iteration):
            completion = await llm.complete(prompt, tier=_tier_for_iteration(iteration))
            response_text = completion.text
            token_used += _count_tokens(response_text)

            action = _extract_json(response_text)
            if action is None:
                # LLM produced unparseable output — treat as final
                log.warning("agent.unparseable_output", text=response_text[:200])
                return AgentResult(
                    answer=response_text,
                    citations=[],
                    bounded=False,
                    iterations=iterations,
                )

            if "final" in action:
                raw_citations = action.get("citations", [])
                final_citations = [c for c in raw_citations if isinstance(c, dict) and "document_slug" in c]
                # Merge any citations accumulated from earlier tool calls.
                return AgentResult(
                    answer=str(action["final"]),
                    citations=final_citations or citations,
                    bounded=False,
                    iterations=iterations,
                )

            if "tool" in action:
                tool_name = action.get("tool", "")
                tool_args = action.get("args", {})

                log.info("agent.tool_call", tool=tool_name, iteration=iteration, tokens_so_far=token_used)
                result = await dispatch(tool_name, tool_args if isinstance(tool_args, dict) else {})
                result_text = json.dumps(result)
                result_tokens = _count_tokens(result_text)
                token_used += result_tokens
                log.debug("agent.tool_result", tool=tool_name, result_tokens=result_tokens, tokens_so_far=token_used)

                prompt = f"{prompt}\n{response_text}\nTool result: {result_text}\n"

                # Collect knowledge citations from tool results
                if "passages" in result:
                    for p in result.get("passages", []):
                        if isinstance(p, dict) and "document_slug" in p:
                            citations.append({
                                "document_slug": p["document_slug"],
                                "heading_path": p.get("heading_path", ""),
                            })
            else:
                # No "final"/"tool" key — the model often writes the prose answer
                # outside the JSON and emits a bare {"citations": [...]} object.
                # Recover the prose; fall back to a synthesis pass if there's none.
                prose = _strip_json_objects(response_text).strip()
                obj_citations = [
                    c for c in action.get("citations", [])
                    if isinstance(c, dict) and "document_slug" in c
                ]
                if len(prose) >= 20:
                    return AgentResult(
                        answer=prose,
                        citations=obj_citations or citations,
                        bounded=False,
                        iterations=iterations,
                    )
                # No usable prose — ask the model once for a clean final answer.
                synth = (
                    f"{prompt}\n{response_text}\n\nNow write the final answer for the user "
                    'as JSON: {"final": "<plain-language answer>", "citations": []}'
                )
                completion = await llm.complete(synth, tier="synthesis")
                synth_action = _extract_json(completion.text)
                if synth_action and "final" in synth_action:
                    return AgentResult(
                        answer=str(synth_action["final"]),
                        citations=obj_citations or citations,
                        bounded=False,
                        iterations=iterations,
                    )
                return AgentResult(
                    answer=_strip_json_objects(completion.text).strip() or str(action),
                    citations=obj_citations or citations,
                    bounded=False,
                    iterations=iterations,
                )

    # Cap hit — synthesise best effort answer
    log.warning("agent.iteration_cap_hit", iterations=iterations)
    synthesis_prompt = (
        f"{prompt}\n\nYou have reached the maximum number of tool calls. "
        "Synthesise the best answer you can from the information gathered so far. "
        'Output: {"final": "<your best answer>", "citations": []}'
    )
    completion = await llm.complete(synthesis_prompt, tier="synthesis")
    action = _extract_json(completion.text)
    if action and "final" in action:
        return AgentResult(
            answer=str(action["final"]),
            citations=citations,
            bounded=True,
            iterations=iterations,
        )
    return AgentResult(
        answer="I've gathered some information but couldn't fully answer your question within the allowed steps. Please try rephrasing or asking a more specific question.",
        citations=citations,
        bounded=True,
        iterations=iterations,
    )


def _tier_for_iteration(iteration: int) -> Tier:
    # Use Flash (synthesis) for the last iteration; Flash-Lite for earlier ones
    return "synthesis" if iteration >= 6 else "mechanical"

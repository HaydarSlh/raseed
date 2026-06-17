"""POST /chat — streamed conversational entry point (FR-001/002, constitution Art. IV)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_active_user
from app.core.config import get_settings
from app.core.exceptions import RailRefusal
from app.db.session import get_rls_session
from app.domain.user import User
from app.infra.llm import get_llm
from app.schemas.chat import ChatRequest, Citation, FinalEvent
from app.services.agent import rails
from app.services.agent import router as agent_router
from app.services.agent.loop import run_agent
from app.services.session_memory import append_turn, load_context

router = APIRouter(prefix="", tags=["chat"])


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user: User = Depends(current_active_user),  # noqa: B008
    session: AsyncSession = Depends(get_rls_session),  # noqa: B008
) -> StreamingResponse:
    settings = get_settings()

    async def _generate():  # noqa: ANN202
        # 1. Input rails check
        try:
            message = await rails.check_input(body.message)
        except RailRefusal as e:
            yield json.dumps({"error": "refusal", "reason": e.reason, "rail": "input"}) + "\n"
            return

        # 2. Load short-term session context
        context = await load_context(body.session_id, ttl=settings.session_ttl_seconds)

        # 3. Route: deterministic or agent
        decision = await agent_router.route(message, session=session, user_id=user.id)

        if decision.route == "deterministic":
            answer = rails.redact(decision.answer or "")
            try:
                answer = await rails.check_output(answer)
            except RailRefusal as e:
                yield json.dumps({"error": "refusal", "reason": e.reason, "rail": "output"}) + "\n"
                return
            yield json.dumps({"delta": answer}) + "\n"
            yield json.dumps(FinalEvent(route="deterministic", citations=[], bounded=False).model_dump()) + "\n"
            await append_turn(body.session_id, "user", message, ttl=settings.session_ttl_seconds)
            await append_turn(body.session_id, "assistant", answer, ttl=settings.session_ttl_seconds)
            return

        # 4. Agent path
        llm = get_llm()
        result = await run_agent(
            message,
            llm=llm,
            context=context,
            max_iterations=settings.agent_max_iterations,
            token_budget=settings.agent_token_budget,
        )

        answer = rails.redact(result.answer)
        try:
            answer = await rails.check_output(answer)
        except RailRefusal as e:
            yield json.dumps({"error": "refusal", "reason": e.reason, "rail": "output"}) + "\n"
            return

        yield json.dumps({"delta": answer}) + "\n"
        citations = [
            Citation(document_slug=c.get("document_slug", ""), heading_path=c.get("heading_path", ""))
            for c in result.citations
        ]
        yield json.dumps(FinalEvent(
            route="agent",
            citations=[c.model_dump() for c in citations],
            bounded=result.bounded,
        ).model_dump()) + "\n"

        await append_turn(body.session_id, "user", message, ttl=settings.session_ttl_seconds)
        await append_turn(body.session_id, "assistant", answer, ttl=settings.session_ttl_seconds)

    return StreamingResponse(_generate(), media_type="application/x-ndjson")

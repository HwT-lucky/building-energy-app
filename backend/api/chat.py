"""Chat API — SSE streaming endpoint for AI-powered analysis."""
import json
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from services.llm_service import (
    chat_stream, get_or_create_session, get_session_history, clear_session,
)
from services.parse_service import get_file_preview

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field("", description="User message")
    file_id: Optional[str] = Field(None, description="Uploaded file ID for context")
    session_id: Optional[str] = Field(None, description="Chat session ID for multi-turn")


@router.post("/chat")
async def chat(req: ChatRequest):
    """Send a message and stream AI response via SSE."""
    session_id = get_or_create_session(req.session_id)

    # If file attached, get preview for context
    file_preview = None
    if req.file_id:
        try:
            preview = get_file_preview(req.file_id, max_rows=10)
            file_preview = {
                "sheets": [
                    {
                        "name": s["name"],
                        "rows": s["total_rows"],
                        "cols": s["total_cols"],
                        "first_5_rows": s["preview_rows"][:5] if s.get("preview_rows") else [],
                    }
                    for s in preview.get("sheets", [])
                ],
                "detection": preview.get("detection", {}),
            }
        except Exception:
            pass  # Preview not critical, continue without it

    return StreamingResponse(
        chat_stream(
            session_id=session_id,
            message=req.message,
            file_id=req.file_id,
            file_preview=file_preview,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history")
async def chat_history(session_id: str):
    """Get chat history for a session."""
    messages = get_session_history(session_id)
    return {"session_id": session_id, "messages": messages}


@router.post("/chat/clear")
async def chat_clear(session_id: str = None):
    """Clear chat session history."""
    if session_id:
        clear_session(session_id)
    return {"status": "ok"}

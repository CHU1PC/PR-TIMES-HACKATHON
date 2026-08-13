from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.calendar import (
    get_authorization_url,
    save_authorization_code,
    get_calendar_service,
    get_events,
)

router = APIRouter(
    prefix="/api/calendar",
    tags=["calendar"],
)

class EventQuery(BaseModel):
    timeMin: str | None = None
    timeMax: str | None = None
    
oauth_sessions = {}


@router.get("/login")
def calendar_login():
    authorization_url, state, code_verifier = get_authorization_url()

    oauth_sessions[state] = code_verifier

    return RedirectResponse(authorization_url)


@router.get("/oauth/callback")
def calendar_callback(
    code: str,
    state: str | None = None,
):
    if not state:
        raise HTTPException(
            status_code=400,
            detail="Missing OAuth state",
        )

    code_verifier = oauth_sessions.pop(state, None)

    if not code_verifier:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth session",
        )

    save_authorization_code(
        code,
        code_verifier,
    )

    return RedirectResponse(
        "http://localhost:5173/"
    )


@router.get("/status")
def calendar_status():
    service = get_calendar_service()

    return {
        "connected": service is not None
    }


@router.post("/events")
def calendar_events(query: EventQuery):
    events = get_events(
        time_min=query.timeMin,
        time_max=query.timeMax,
    )

    if events is None:
        return {
            "connected": False,
            "events": [],
        }

    return {
        "connected": True,
        "events": events,
    }
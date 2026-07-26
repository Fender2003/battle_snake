from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI

from agent import VALID_MOVES, build_agent

AGENT_NAME = os.getenv("SNAKE_AGENT", "advanced")
AGENT = build_agent(AGENT_NAME)
app = FastAPI(title="Battlesnake Blackout Local API")


@app.get("/")
def info() -> dict[str, str]:
    return {
        "apiversion": AGENT.apiversion,
        "author": AGENT.author,
        "color": AGENT.color,
    }


@app.post("/start")
def start(game_state: dict[str, Any]) -> dict[str, str]:
    AGENT.start(game_state, game_state["you"])
    return {"status": "ok"}


@app.post("/move")
def move(game_state: dict[str, Any]) -> dict[str, str]:
    decision = AGENT.move(game_state, game_state["you"])
    if decision not in VALID_MOVES:
        decision = "up"
    return {"move": decision}


@app.post("/end")
def end(game_state: dict[str, Any]) -> dict[str, str]:
    AGENT.end(game_state, game_state["you"])
    return {"status": "ok"}

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

VALID_MOVES = ("up", "down", "left", "right")
MOVE_DELTAS: dict[str, tuple[int, int]] = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}


class BaseAgent(ABC):
    name: str = "base-agent"
    color: str = "#00ff00"
    author: str = "Skadoosh"

    def start(self, game_state: dict[str, Any], you: dict[str, Any]) -> None:
        _ = game_state, you

    @abstractmethod
    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        raise NotImplementedError

    def end(self, game_state: dict[str, Any], you: dict[str, Any]) -> None:
        _ = game_state, you


def next_position(pos: tuple[int, int], move: str) -> tuple[int, int]:
    dx, dy = MOVE_DELTAS[move]
    return pos[0] + dx, pos[1] + dy


def is_in_bounds(pos: tuple[int, int], width: int, height: int) -> bool:
    return 0 <= pos[0] < width and 0 <= pos[1] < height


def parse_point(point: dict[str, int]) -> tuple[int, int]:
    return point["x"], point["y"]


def legal_moves(game_state: dict[str, Any], you: dict[str, Any]) -> list[str]:
    width = game_state["board"]["width"]
    height = game_state["board"]["height"]
    body = [parse_point(p) for p in you["body"]]
    head = parse_point(you["head"])

    blocked: set[tuple[int, int]] = set()
    for snake in game_state["board"]["snakes"]:
        points = [parse_point(p) for p in snake["body"]]
        if snake["id"] == you["id"] and len(points) > 1:
            blocked.update(points[:-1])
        else:
            blocked.update(points)

    legal: list[str] = []
    for move in VALID_MOVES:
        nxt = next_position(head, move)
        if not is_in_bounds(nxt, width, height):
            continue
        if nxt in blocked:
            continue
        if len(body) > 1 and nxt == body[1]:
            continue
        legal.append(move)
    return legal


def build_agent(name: str) -> BaseAgent:
    from agents.advanced_agent import AdvancedAgent
    from agents.greedy_food_agent import GreedyFoodAgent
    from agents.random_agent import RandomAgent

    key = name.lower().strip()
    registry: dict[str, BaseAgent] = {
        "random": RandomAgent(),
        "greedy": GreedyFoodAgent(),
        "advanced": AdvancedAgent(),
    }
    if key not in registry:
        raise ValueError(f"Unknown agent '{name}'. Available: {sorted(registry.keys())}")
    return registry[key]

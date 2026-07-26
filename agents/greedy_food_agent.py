from __future__ import annotations

from typing import Any

from agent import BaseAgent, legal_moves, next_position, parse_point


class GreedyFoodAgent(BaseAgent):
    name = "greedy"
    color = "#ffaa00"
    author = "GreedyFoodBot"

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        legal = legal_moves(game_state, you)
        if not legal:
            return "up"
        head = parse_point(you["head"])
        foods = [parse_point(food) for food in game_state["board"]["food"]]
        if not foods:
            return legal[0]

        def score(move: str) -> int:
            nxt = next_position(head, move)
            return min(abs(nxt[0] - fx) + abs(nxt[1] - fy) for fx, fy in foods)

        return min(legal, key=score)

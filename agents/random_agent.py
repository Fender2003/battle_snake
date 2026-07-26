from __future__ import annotations

import random
from typing import Any

from agent import BaseAgent, VALID_MOVES, legal_moves


class RandomAgent(BaseAgent):
    name = "random"
    color = "#cccccc"
    author = "RandomBot"

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        legal = legal_moves(game_state, you)
        if legal:
            return random.choice(legal)
        return random.choice(list(VALID_MOVES))

# agents/aggressive_agent.py
from __future__ import annotations

from typing import Any

from agent import BaseAgent, legal_moves, next_position, parse_point


class AggressiveAgent(BaseAgent):
    """Seeks H2H kills when longer, flees when shorter."""
    name = "aggressive"
    apiversion = "1"
    color = "#ff0000"
    author = "AggressiveBot"

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        legal = legal_moves(game_state, you)
        if not legal:
            return "up"
        
        head = parse_point(you["head"])
        your_len = len(you["body"])
        
        opps = []
        for s in game_state["board"].get("snakes", []):
            if s["id"] == you["id"]:
                continue
            body = [parse_point(p) for p in s.get("body", [])]
            if body:
                opps.append({"head": body[0], "len": len(body)})
        
        # Find targets (shorter opponents) and threats (longer opponents)
        targets = [o for o in opps if your_len > o["len"]]
        threats = [o for o in opps if your_len <= o["len"]]
        
        # Try to move toward a target
        if targets:
            target = min(targets, key=lambda o: abs(o["head"][0] - head[0]) + abs(o["head"][1] - head[1]))
            best_move = min(legal, key=lambda m: abs(next_position(head, m)[0] - target["head"][0]) + 
                                                       abs(next_position(head, m)[1] - target["head"][1]))
            return best_move
        
        # Flee from threats
        if threats:
            threat = min(threats, key=lambda o: abs(o["head"][0] - head[0]) + abs(o["head"][1] - head[1]))
            best_move = max(legal, key=lambda m: abs(next_position(head, m)[0] - threat["head"][0]) + 
                                                      abs(next_position(head, m)[1] - threat["head"][1]))
            return best_move
        
        return legal[0]
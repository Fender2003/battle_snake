# agents/defensive_agent.py
from __future__ import annotations

from collections import deque
from typing import Any

from agent import BaseAgent, legal_moves, next_position, parse_point


class DefensiveAgent(BaseAgent):
    """Maximizes space, follows own tail, never takes risks."""
    name = "defensive"
    apiversion = "1"
    color = "#0000ff"
    author = "DefensiveBot"

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        legal = legal_moves(game_state, you)
        if not legal:
            return "up"
        
        board = game_state["board"]
        W, H = board["width"], board["height"]
        head = parse_point(you["head"])
        body = [parse_point(p) for p in you["body"]]
        tail = body[-1]
        
        opps = []
        for s in board.get("snakes", []):
            if s["id"] == you["id"]:
                continue
            b = [parse_point(p) for p in s.get("body", [])]
            if b:
                opps.append({"body": b})
        
        # Maximize space, with bonus for moving toward tail
        best_move = legal[0]
        best_score = -1e18
        
        for m in legal:
            nxt = next_position(head, m)
            space = self._floodfill(nxt, [body] + [o["body"] for o in opps], W, H)
            tail_dist = abs(nxt[0] - tail[0]) + abs(nxt[1] - tail[1])
            score = space * 2.0 - tail_dist * 0.5
            if score > best_score:
                best_score = score
                best_move = m
        
        return best_move
    
    def _floodfill(self, start, bodies, W, H):
        blocked = set()
        for b in bodies:
            if b:
                blocked.update(b[:-1] if len(b) > 1 else b)
        if start in blocked:
            return 0
        visited = {start}
        q = deque([start])
        count = 0
        while q and count < 60:
            x, y = q.popleft()
            count += 1
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H:
                    n = (nx, ny)
                    if n not in visited and n not in blocked:
                        visited.add(n)
                        q.append(n)
        return count
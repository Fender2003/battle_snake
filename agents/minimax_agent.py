# agents/minimax_agent.py
from __future__ import annotations

import time
from collections import deque
from typing import Any, Optional

from agent import BaseAgent, legal_moves, next_position, parse_point


class MinimaxAgent(BaseAgent):
    """Simple depth-2 minimax (no alpha-beta, no transposition tables)."""
    name = "minimax"
    apiversion = "1"
    color = "#ff00ff"
    author = "MinimaxBot"

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        board = game_state["board"]
        W, H = board["width"], board["height"]
        your_body = [parse_point(p) for p in you["body"]]
        your_head = your_body[0]
        your_len = len(your_body)
        
        opps = []
        for s in board.get("snakes", []):
            if s["id"] == you["id"]:
                continue
            body = [parse_point(p) for p in s.get("body", [])]
            if body:
                opps.append({"body": body, "head": body[0], "len": len(body)})
        
        moves = self._safe_moves(your_head, your_body, your_len, opps, W, H)
        if not moves:
            return legal_moves(game_state, you)[0] if legal_moves(game_state, you) else "up"
        
        best_move = moves[0]
        best_score = -1e18
        
        for m in moves:
            score = self._min_score(your_head, your_body, your_len, m, opps, W, H, depth=1)
            if score > best_score:
                best_score = score
                best_move = m
        
        return best_move
    
    def _min_score(self, head, body, my_len, my_move, opps, W, H, depth):
        """Get worst-case score from opponent responses."""
        my_new_head = next_position(head, my_move)
        
        # Opponents pick moves
        opp_moves_list = []
        for opp in opps:
            others = [{"body": body, "head": head, "len": my_len}]
            for o in opps:
                if o is not opp:
                    others.append(o)
            moves = self._safe_moves(opp["head"], opp["body"], opp["len"], others, W, H)
            if moves:
                opp_moves_list.append((opp, moves))
        
        if not opp_moves_list:
            return self._evaluate(my_new_head, body, my_len, opps, W, H)
        
        min_score = 1e18
        for opp, moves in opp_moves_list:
            for om in moves:
                opp_new_head = next_position(opp["head"], om)
                # Simplified: just evaluate after one opponent moves
                score = self._evaluate(my_new_head, body, my_len, 
                                      [{"head": opp_new_head, "body": opp["body"], "len": opp["len"]}], 
                                      W, H)
                min_score = min(min_score, score)
        
        return min_score
    
    def _evaluate(self, my_head, my_body, my_len, opps, W, H):
        """Simple evaluation: space + length."""
        my_space = self._floodfill(my_head, [my_body] + [o["body"] for o in opps], W, H)
        score = my_space * 2.0
        
        for opp in opps:
            opp_space = self._floodfill(opp["head"], [my_body] + [o["body"] for o in opps], W, H)
            score -= opp_space
            dist = abs(my_head[0] - opp["head"][0]) + abs(my_head[1] - opp["head"][1])
            if dist == 1:
                if my_len > opp["len"]:
                    score += 100
                else:
                    score -= 100
        
        return score
    
    def _safe_moves(self, head, body, my_len, opps, W, H):
        blocked = set()
        for opp in opps:
            b = opp["body"]
            blocked.update(b[:-1] if len(b) > 1 else b)
        blocked.update(body[:-1] if len(body) > 1 else body)
        
        out = []
        for m in ("up", "down", "left", "right"):
            nx, ny = next_position(head, m)
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            if (nx, ny) in blocked:
                continue
            dead = False
            for opp in opps:
                if abs(opp["head"][0] - nx) + abs(opp["head"][1] - ny) == 1:
                    if my_len <= opp["len"]:
                        dead = True
                        break
            if not dead:
                out.append(m)
        return out
    
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
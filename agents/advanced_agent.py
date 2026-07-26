from __future__ import annotations

from typing import Any, Optional
from collections import deque

from agent import BaseAgent, legal_moves, next_position, parse_point


class AdvancedAgent(BaseAgent):
    """
    High-performance Battlesnake with:
    - Head-to-head collision detection
    - Opponent threat awareness
    - Efficient space evaluation
    - Tail chasing for survival
    - Optimized for < 100ms execution
    """

    name = "advanced"
    apiversion = "1"
    color = "#00ff00"
    author = "Skadoosh"

    # Scoring weights
    W_SPACE = 100.0
    W_FOOD = 25.0
    W_MOMENTUM = 8.0
    W_TAIL_CHASE = 20.0
    W_HEAD_TO_HEAD_PENALTY = 100.0
    W_OPPONENT_THREAT = 40.0

    # Thresholds
    LOW_HEALTH = 60
    STARVING = 30
    MIN_SPACE_THRESHOLD = 0.25  # need at least 25% of board

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        try:
            return self._move_impl(game_state, you)
        except Exception:
            return self._fallback(game_state, you)

    def _fallback(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        try:
            legal = legal_moves(game_state, you) or ["up", "down", "left", "right"]
            return legal[0]
        except Exception:
            return "up"

    def _move_impl(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        board = game_state.get("board", {})
        width = board.get("width", 11)
        height = board.get("height", 11)
        snakes = board.get("snakes", [])
        foods = [parse_point(f) for f in board.get("food", [])]
        
        you_id = you.get("id")
        your_body = [parse_point(p) for p in you.get("body", [])]
        your_length = len(your_body)
        your_health = you.get("health", 100)
        head = your_body[0]
        
        # Build blocked cells and track opponents
        blocked = set()
        opponent_heads = []  # (pos, length, adjacent_cells)
        
        for snake in snakes:
            body = [parse_point(p) for p in snake.get("body", [])]
            if not body:
                continue
            
            # Add body except tail (tail will move)
            if len(body) > 1:
                blocked.update(body[:-1])
            else:
                blocked.update(body)
            
            # Track opponent heads for threat detection
            if snake.get("id") != you_id:
                opp_head = body[0]
                opp_len = len(body)
                # Pre-compute where this opponent can move
                opp_moves = set()
                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nx, ny = opp_head[0] + dx, opp_head[1] + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        opp_moves.add((nx, ny))
                opponent_heads.append((opp_head, opp_len, opp_moves))
        
        # Get legal moves
        legal = legal_moves(game_state, you)
        if not legal:
            return "up"
        
        # Filter safe moves
        safe_moves = []
        for m in legal:
            nxt = next_position(head, m)
            if not (0 <= nxt[0] < width and 0 <= nxt[1] < height):
                continue
            if nxt in blocked:
                continue
            safe_moves.append((m, nxt))
        
        if not safe_moves:
            return legal[0]
        
        # If only one safe move, take it
        if len(safe_moves) == 1:
            return safe_moves[0][0]
        
        # Score moves
        move_scores = {}
        current_dir = self._get_heading(you)
        your_tail = your_body[-1] if your_body else head
        
        for m, nxt in safe_moves:
            score = 0.0
            
            # 1. Head-to-head detection (CRITICAL)
            h2h_danger = False
            for opp_head, opp_len, opp_moves in opponent_heads:
                if nxt in opp_moves:
                    # We'd collide head-to-head
                    if your_length <= opp_len:
                        # We'd lose or tie - huge penalty
                        score -= self.W_HEAD_TO_HEAD_PENALTY
                        h2h_danger = True
                    else:
                        # We'd win - small bonus
                        score += 10.0
            
            # 2. Opponent threat detection
            for opp_head, opp_len, opp_moves in opponent_heads:
                # Check if opponent could move into our path next turn
                opp_dist = abs(opp_head[0] - nxt[0]) + abs(opp_head[1] - nxt[1])
                if opp_dist <= 2 and opp_len >= your_length:
                    # Dangerous opponent nearby
                    score -= self.W_OPPONENT_THREAT * (3 - opp_dist) / 2
            
            # 3. Space evaluation (floodfill)
            sim_blocked = blocked.copy()
            sim_blocked.discard(nxt)
            
            your_space = self._floodfill_fast(nxt, width, height, sim_blocked)
            space_ratio = your_space / (width * height)
            
            # Penalize if space is too small
            if space_ratio < self.MIN_SPACE_THRESHOLD:
                score -= 50.0 * (self.MIN_SPACE_THRESHOLD - space_ratio)
            
            score += self.W_SPACE * space_ratio
            
            # 4. Food seeking (only when needed)
            if foods and your_health < self.LOW_HEALTH:
                best_food_score = 0.0
                urgency = 2.5 if your_health < self.STARVING else 1.0
                
                for food in foods:
                    dist = abs(food[0] - nxt[0]) + abs(food[1] - nxt[1])
                    if dist > 0:
                        food_score = urgency / dist
                        best_food_score = max(best_food_score, food_score)
                
                score += self.W_FOOD * best_food_score
            
            # 5. Momentum (prefer straight lines)
            if current_dir and m == current_dir:
                score += self.W_MOMENTUM
            
            # 6. Tail chasing (excellent for survival when not hungry)
            if your_health >= self.LOW_HEALTH and not h2h_danger:
                tail_dist = abs(your_tail[0] - nxt[0]) + abs(your_tail[1] - nxt[1])
                if 1 <= tail_dist <= 8:  # chase if close but not on top
                    score += self.W_TAIL_CHASE * (1.0 / tail_dist)
            
            move_scores[m] = score
        
        return self._pick_best(move_scores, current_dir)

    def _floodfill_fast(self, start: tuple[int, int], width: int, height: int, 
                        blocked: set[tuple[int, int]]) -> int:
        """Optimized floodfill with early termination."""
        if start in blocked:
            return 0
        
        # Use simple BFS with limited depth
        visited = {start}
        queue = deque([start])
        count = 0
        max_count = (width * height) // 2  # Don't need to count beyond this
        
        while queue and count < max_count:
            x, y = queue.popleft()
            count += 1
            
            # Inline neighbor checking for speed
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    neighbor = (nx, ny)
                    if neighbor not in visited and neighbor not in blocked:
                        visited.add(neighbor)
                        queue.append(neighbor)
        
        return count

    def _get_heading(self, you: dict[str, Any]) -> Optional[str]:
        body = you.get("body", [])
        if len(body) < 2:
            return None
        
        head = parse_point(body[0])
        neck = parse_point(body[1])
        
        dx, dy = head[0] - neck[0], head[1] - neck[1]
        if dx == 0 and dy == 1:
            return "up"
        if dx == 0 and dy == -1:
            return "down"
        if dx == 1 and dy == 0:
            return "right"
        if dx == -1 and dy == 0:
            return "left"
        return None

    def _pick_best(self, move_scores: dict[str, float], current_dir: Optional[str]) -> str:
        if not move_scores:
            return "up"
        
        best_score = max(move_scores.values())
        tied = [m for m, s in move_scores.items() if s == best_score]
        
        if len(tied) == 1:
            return tied[0]
        
        # Tiebreak: prefer current direction (reduces zigzagging)
        if current_dir and current_dir in tied:
            return current_dir
        
        # Tiebreak: prefer up/right (slight edge bias)
        for direction in ["up", "right", "down", "left"]:
            if direction in tied:
                return direction
        
        return sorted(tied)[0]
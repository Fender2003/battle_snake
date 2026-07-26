from __future__ import annotations

from typing import Any, Optional

from agent import BaseAgent, legal_moves, next_position, parse_point
from utils.floodfill import estimate_space
from utils.pathfinding import bfs_path


class AdvancedAgent(BaseAgent):
    """
    Deliberately simple and stable. Decision order:

      1. SAFETY FILTER (hard): throw out any move that collides with a
         snake body. This is a filter, not a score -- an unsafe move can
         never win no matter how good its other numbers look.
      2. Among safe moves, rank by floodfill space (don't get trapped).
      3. Add a real MOMENTUM term -- a bonus for continuing your current
         heading. This is what was missing before: without it, two moves
         with very close (but not exactly equal) scores can trade the lead
         turn to turn as the board shifts slightly, which looks like
         random zigzagging (e.g. "up" then "down" then "up"). Momentum
         damps that out by making "keep going the way you were going"
         worth something concrete, not just a tiebreaker for exact ties.
      4. Food is only weighted meaningfully when health is actually low --
         otherwise it's a small nudge, not a competing priority.

    No offense/hunting, no multi-ply trap lookahead. Those add real value
    eventually, but they're exactly the kind of thing that turns a stable
    snake into an erratic one if a heuristic is even slightly off, so
    they're left out until this simpler core is confirmed solid.
    """

    name = "advanced"
    apiversion = "1"
    color = "#00ff00"
    author = "Skadoosh"

    W_SPACE = 50.0
    W_FOOD_BASE = 8.0
    W_MOMENTUM = 12.0  # real scoring term, not just a tiebreak

    LOW_HEALTH_THRESHOLD = 70
    STARVING_THRESHOLD = 30

    # ------------------------------------------------------------------ #
    # Entry point -- never allowed to raise
    # ------------------------------------------------------------------ #

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        try:
            result = self._move_impl(game_state, you)
            if result:
                return result
        except Exception:
            pass
        return self._safe_fallback(game_state, you)

    def _safe_fallback(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        try:
            legal = legal_moves(game_state, you) or ["up", "down", "left", "right"]
            head = parse_point(you.get("head", {"x": 0, "y": 0}))
            board = game_state.get("board", {})
            width = board.get("width", 11)
            height = board.get("height", 11)

            blocked = set()
            for snake in board.get("snakes", []) or []:
                for p in snake.get("body") or []:
                    try:
                        blocked.add(parse_point(p))
                    except Exception:
                        continue

            safe = []
            for m in legal:
                try:
                    nxt = next_position(head, m)
                except Exception:
                    continue
                if nxt in blocked:
                    continue
                if not (0 <= nxt[0] < width and 0 <= nxt[1] < height):
                    continue
                safe.append(m)

            if not safe:
                return legal[0]

            current_dir = self._current_heading(you)
            if current_dir and current_dir in safe:
                return current_dir
            return sorted(safe)[0]
        except Exception:
            return "up"

    # ------------------------------------------------------------------ #
    # Main logic
    # ------------------------------------------------------------------ #

    def _move_impl(self, game_state: dict[str, Any], you: dict[str, Any]) -> Optional[str]:
        legal = legal_moves(game_state, you)
        if not legal:
            return None

        board = game_state.get("board") or {}
        width, height = board.get("width"), board.get("height")
        if not width or not height:
            return None
        if not you.get("head"):
            return None

        head = parse_point(you["head"])
        your_health = int(you.get("health") if you.get("health") is not None else 100)
        foods = [parse_point(f) for f in (board.get("food") or [])]
        blocked = self._blocked_cells(game_state, you)
        current_dir = self._current_heading(you)
        food_urgency = self._food_urgency(your_health)

        # --- Step 1: hard safety filter ---
        safe_moves = []
        for m in legal:
            try:
                nxt = next_position(head, m)
            except Exception:
                continue
            if nxt in blocked:
                continue
            if not (0 <= nxt[0] < width and 0 <= nxt[1] < height):
                continue
            safe_moves.append((m, nxt))

        if not safe_moves:
            # nothing is safe -- every option dies; just return any legal
            # move rather than crash, the outcome is the same either way.
            return legal[0]

        # --- Step 2/3/4: score only the survivors ---
        move_scores: dict[str, float] = {}
        for m, nxt in safe_moves:
            sim_blocked = set(blocked)
            sim_blocked.discard(nxt)

            space = estimate_space(
                start=nxt,
                width=width,
                height=height,
                blocked=sim_blocked,
                limit=width * height,
            )
            space_score = space / max(1, width * height)

            food_score = 0.0
            if foods:
                try:
                    path = bfs_path(nxt, set(foods), width, height, sim_blocked)
                    if path:
                        food_score = 1.0 / max(1, len(path) - 1)
                except Exception:
                    food_score = 0.0

            momentum_bonus = 1.0 if (current_dir and m == current_dir) else 0.0

            move_scores[m] = (
                (self.W_SPACE * space_score)
                + (self.W_FOOD_BASE * food_urgency * food_score)
                + (self.W_MOMENTUM * momentum_bonus)
            )

        return self._pick_best(move_scores, you)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _blocked_cells(self, game_state: dict[str, Any], you: dict[str, Any]) -> set[tuple[int, int]]:
        blocked: set[tuple[int, int]] = set()
        for snake in (game_state.get("board", {}).get("snakes") or []):
            raw_body = snake.get("body") or []
            if not raw_body:
                continue
            try:
                body = [parse_point(p) for p in raw_body]
            except Exception:
                continue
            # tail assumed to vacate next turn (simple and reliable)
            if len(body) > 1:
                blocked.update(body[:-1])
            else:
                blocked.update(body)
        return blocked

    def _current_heading(self, you: dict[str, Any]) -> Optional[str]:
        body = you.get("body") or []
        if len(body) < 2:
            return None
        try:
            head = parse_point(body[0])
            neck = parse_point(body[1])
        except Exception:
            return None

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

    def _food_urgency(self, health: int) -> float:
        if health >= self.LOW_HEALTH_THRESHOLD:
            return 0.3
        if health <= self.STARVING_THRESHOLD:
            return 2.0
        span = max(1, self.LOW_HEALTH_THRESHOLD - self.STARVING_THRESHOLD)
        progress = (self.LOW_HEALTH_THRESHOLD - health) / span
        return 0.3 + progress * (2.0 - 0.3)

    def _pick_best(self, move_scores: dict[str, float], you: dict[str, Any]) -> str:
        best_score = max(move_scores.values())
        tied = [m for m, s in move_scores.items() if s == best_score]
        if len(tied) == 1:
            return tied[0]
        current_dir = self._current_heading(you)
        if current_dir and current_dir in tied:
            return current_dir
        return sorted(tied)[0]
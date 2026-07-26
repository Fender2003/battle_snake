from __future__ import annotations

from typing import Any, Optional

from agent import BaseAgent, legal_moves, next_position, parse_point
from utils.floodfill import estimate_space
from utils.pathfinding import bfs_path


class AdvancedAgent(BaseAgent):
    """
    Same core logic as the version that performed well in practice:
    survival check -> space (flood fill) -> health-scaled food pull ->
    head-to-head collision avoidance. Nothing fancier layered on top,
    because the fancier version (trap lookahead / offense scoring reaching
    into fields that can be missing) is what was causing crashes and worse
    play.

    What changed here, specifically to fix crashes and reliability:
      1. move() is wrapped so ANY unexpected exception falls back to a
         minimal, always-safe decision instead of the process dying mid-game
         (a crash forfeits the turn far worse than a mediocre move would).
      2. Every board-state field is read defensively (.get with a default,
         guarded conversions) so a missing/odd field never raises.
      3. Food urgency is a smooth ramp instead of a hard 70/30 cutoff, so
         behavior doesn't jump discontinuously right at those health values.
      4. Offense scoring is back, but conservatively: it only ever adds
         bonus to a move that has ALREADY been confirmed to have zero
         collision risk and reasonable space -- it can never be the reason
         a risky move gets picked.
    """

    name = "advanced"
    apiversion = "1"
    color = "#00ff00"
    author = "Skadoosh"

    W_SURVIVAL = 100.0
    W_SPACE = 50.0
    W_FOOD_BASE = 8.0
    W_COLLISION = 55.0
    W_OFFENSE = 10.0

    LOW_HEALTH_THRESHOLD = 70
    STARVING_THRESHOLD = 30
    HUNT_RANGE = 4
    MIN_SAFE_SPACE_FOR_OFFENSE = 0.15  # only hunt if the move is roomy too

    # ------------------------------------------------------------------ #
    # Entry point -- never allowed to raise
    # ------------------------------------------------------------------ #

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        try:
            result = self._move_impl(game_state, you)
            if result:
                return result
        except Exception:
            pass  # fall through to the safe fallback below

        return self._safe_fallback(game_state, you)

    def _safe_fallback(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        """
        Minimal, defensive-only decision used if the main logic throws for
        any reason. Just avoids obviously fatal squares; no scoring, no
        fancy structures, so it can't itself fail the same way.
        """
        try:
            legal = legal_moves(game_state, you) or ["up", "down", "left", "right"]
            head = parse_point(you.get("head", {"x": 0, "y": 0}))
            board = game_state.get("board", {})
            width = board.get("width", 11)
            height = board.get("height", 11)

            blocked: set[tuple[int, int]] = set()
            for snake in board.get("snakes", []) or []:
                body = snake.get("body") or []
                for p in body:
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
        width = board.get("width")
        height = board.get("height")
        if not width or not height:
            return None

        if not you.get("head"):
            return None
        head = parse_point(you["head"])

        your_len = max(1, int(you.get("length") or 1))
        your_health = int(you.get("health") if you.get("health") is not None else 100)
        foods = [parse_point(f) for f in (board.get("food") or [])]

        blocked = self._blocked_cells(game_state, you)
        enemies = self._enemy_info(game_state, you)
        food_urgency = self._food_urgency(your_health)

        move_scores: dict[str, float] = {}

        for m in legal:
            try:
                nxt = next_position(head, m)
            except Exception:
                continue

            if nxt in blocked:
                move_scores[m] = -1e6
                continue

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

            collision_risk = self._head_to_head_risk(nxt, enemies, your_len)

            offense_score = 0.0
            if collision_risk == 0.0 and space_score >= self.MIN_SAFE_SPACE_FOR_OFFENSE:
                offense_score = self._offense_score(nxt, enemies, your_len)

            move_scores[m] = (
                self.W_SURVIVAL
                + (self.W_SPACE * space_score)
                + (self.W_FOOD_BASE * food_urgency * food_score)
                + (self.W_OFFENSE * offense_score)
                - (self.W_COLLISION * collision_risk)
            )

        if not move_scores:
            return None

        return self._pick_best(move_scores, you)

    def _pick_best(self, move_scores: dict[str, float], you: dict[str, Any]) -> str:
        """
        Break ties deterministically and sensibly instead of relying on
        dict/list ordering (which silently favors whatever came first --
        e.g. "up" -- and can look like a random direction change when
        several moves score the same).

        Preference order for ties: continue in the current heading first
        (less erratic movement), then fall back to a deterministic choice.
        """
        best_score = max(move_scores.values())
        tied = [m for m, s in move_scores.items() if s == best_score]

        if len(tied) == 1:
            return tied[0]

        current_dir = self._current_heading(you)
        if current_dir and current_dir in tied:
            return current_dir

        # Still tied with no heading preference available: pick
        # deterministically (sorted) rather than dict-insertion order.
        return sorted(tied)[0]

    def _current_heading(self, you: dict[str, Any]) -> Optional[str]:
        """Infer current direction of travel from the last two body segments."""
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

    # ------------------------------------------------------------------ #
    # Board state helpers (defensive: never assume a field is present)
    # ------------------------------------------------------------------ #

    def _blocked_cells(self, game_state: dict[str, Any], you: dict[str, Any]) -> set[tuple[int, int]]:
        blocked: set[tuple[int, int]] = set()
        you_id = you.get("id")

        for snake in (game_state.get("board", {}).get("snakes") or []):
            raw_body = snake.get("body") or []
            if not raw_body:
                continue

            try:
                body = [parse_point(p) for p in raw_body]
            except Exception:
                continue

            # Assume the tail vacates next turn (simpler and, per testing,
            # more reliable than trying to detect "just ate" from health).
            if len(body) > 1:
                blocked.update(body[:-1])
            else:
                blocked.update(body)

        return blocked

    def _enemy_info(self, game_state: dict[str, Any], you: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        you_id = you.get("id")

        for snake in (game_state.get("board", {}).get("snakes") or []):
            if snake.get("id") == you_id:
                continue
            if not snake.get("body") or not snake.get("head"):
                continue
            try:
                out.append(
                    {
                        "head": parse_point(snake["head"]),
                        "length": int(snake.get("length") or 0),
                    }
                )
            except Exception:
                continue

        return out

    # ------------------------------------------------------------------ #
    # Scoring components
    # ------------------------------------------------------------------ #

    def _food_urgency(self, health: int) -> float:
        """Smooth ramp instead of a hard cutoff, so behavior near the
        threshold values doesn't jump discontinuously."""
        if health >= self.LOW_HEALTH_THRESHOLD:
            return 0.3
        if health <= self.STARVING_THRESHOLD:
            return 2.0
        span = max(1, self.LOW_HEALTH_THRESHOLD - self.STARVING_THRESHOLD)
        progress = (self.LOW_HEALTH_THRESHOLD - health) / span
        return 0.3 + progress * (2.0 - 0.3)

    def _head_to_head_risk(
        self,
        target: tuple[int, int],
        enemies: list[dict[str, Any]],
        your_length: int,
    ) -> float:
        risk = 0.0
        for enemy in enemies:
            ehead, elen = enemy["head"], enemy["length"]
            dist = abs(ehead[0] - target[0]) + abs(ehead[1] - target[1])
            if dist == 1 and elen >= your_length:
                risk = max(risk, 1.0)
            elif dist == 2 and elen >= your_length:
                risk = max(risk, 0.4)
        return risk

    def _offense_score(
        self,
        target: tuple[int, int],
        enemies: list[dict[str, Any]],
        your_length: int,
    ) -> float:
        """Only ever adds a bonus -- called from a context where the move
        is already confirmed collision-free and has decent space, so this
        can never be the reason a dangerous move wins."""
        best = 0.0
        for enemy in enemies:
            ehead, elen = enemy["head"], enemy["length"]
            if elen >= your_length:
                continue
            dist = abs(ehead[0] - target[0]) + abs(ehead[1] - target[1])
            if dist == 0:
                continue
            if dist <= self.HUNT_RANGE:
                best = max(best, 1.0 / dist)
        return best
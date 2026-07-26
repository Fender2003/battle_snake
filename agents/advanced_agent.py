# from __future__ import annotations

# from typing import Any

# from agent import BaseAgent, legal_moves, next_position, parse_point
# from utils.floodfill import estimate_space
# from utils.pathfinding import a_star_path, bfs_path


# class AdvancedAgent(BaseAgent):
#     name = "advanced"
#     apiversion = "1"
#     color = "#00ff00"
#     author = "Skadoosh"

#     def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
#         legal = legal_moves(game_state, you)
#         if not legal:
#             return "up"

#         width = game_state["board"]["width"]
#         height = game_state["board"]["height"]
#         head = parse_point(you["head"])
#         your_len = int(you["length"])
#         your_health = int(you.get("health", 100))
#         foods = [parse_point(food) for food in game_state["board"]["food"]]

#         blocked = self._blocked_cells(game_state, you)
#         enemy_heads = self._enemy_heads(game_state, you)
#         move_scores: dict[str, float] = {}

#         for move in legal:
#             nxt = next_position(head, move)
#             simulated_blocked = set(blocked)
#             simulated_blocked.discard(nxt)

#             survival_probability = 1.0
#             if nxt in blocked:
#                 survival_probability = 0.0

#             space = estimate_space(
#                 start=nxt,
#                 width=width,
#                 height=height,
#                 blocked=simulated_blocked,
#                 limit=width * height,
#             )
#             space_score = space / (width * height)

#             food_score = 0.0
#             if foods:
#                 path = bfs_path(nxt, set(foods), width, height, simulated_blocked)
#                 if path:
#                     food_score = 1.0 / max(1, len(path) - 1)

#                     if your_health > 70:
#                         food_score *= 0.3
#                     elif your_health < 30:
#                         food_score *= 2.0
                        
#             collision_risk = self._head_to_head_risk(
#                 target=nxt,
#                 enemy_heads=enemy_heads,
#                 your_length=your_len,
#             )

#             # a_star_bonus = 0.0
#             # if foods:
#             #     nearest_food = min(foods, key=lambda f: abs(nxt[0] - f[0]) + abs(nxt[1] - f[1]))
#             #     if a_star_path(nxt, nearest_food, width, height, simulated_blocked):
#             #         a_star_bonus = 0.15

#             move_scores[move] = (
#                 (100.0 * survival_probability)
#                 + (50.0 * space_score)
#                 + (8.0 * food_score)
#                 - (55.0 * collision_risk)
#             )

#         return max(move_scores, key=move_scores.get)

#     def _blocked_cells(self, game_state: dict[str, Any], you: dict[str, Any]) -> set[tuple[int, int]]:
#         blocked: set[tuple[int, int]] = set()
#         for snake in game_state["board"]["snakes"]:
#             body = [parse_point(p) for p in snake["body"]]
#             if not body:
#                 continue
#             if snake["id"] == you["id"] and len(body) > 1:
#                 blocked.update(body[:-1])
#             else:
#                 if len(body) > 1:
#                     blocked.update(body[:-1])
#                 else:
#                     blocked.update(body)

#         return blocked

#     def _enemy_heads(self, game_state: dict[str, Any], you: dict[str, Any]) -> list[tuple[tuple[int, int], int]]:
#         out: list[tuple[tuple[int, int], int]] = []

#         for snake in game_state["board"]["snakes"]:
#             if snake["id"] == you["id"]:
#                 continue

#             # Ignore dead snakes
#             if not snake.get("head") or not snake.get("body"):
#                 continue

#             out.append(
#                 (
#                     parse_point(snake["head"]),
#                     int(snake.get("length") or 0)
#                 )
#             )

#         return out

#     def _head_to_head_risk(
#         self,
#         target: tuple[int, int],
#         enemy_heads: list[tuple[tuple[int, int], int]],
#         your_length: int,
        
#     ) -> float:
#         risk = 0.0
#         for enemy_head, enemy_len in enemy_heads:
#             dist = abs(enemy_head[0] - target[0]) + abs(enemy_head[1] - target[1])
#             if dist == 1 and enemy_len >= your_length:
#                 risk = max(risk, 1.0)
#             elif dist == 2 and enemy_len >= your_length:
#                 risk = max(risk, 0.4)
#         return risk




from __future__ import annotations

from typing import Any

from agent import BaseAgent, legal_moves, next_position, parse_point
from utils.floodfill import estimate_space
from utils.pathfinding import bfs_path


class AdvancedAgent(BaseAgent):
    """
    Heuristic Battlesnake agent with:
      - health-aware food urgency (stops chasing food when full)
      - single reachability check instead of duplicated BFS + A*
      - tail-chase safety (enemy tails that will vacate aren't treated as walls)
      - offensive scoring (rewards pressuring weaker snakes, not just avoiding them)
      - 1-ply lookahead against nearby threats to catch traps a pure
        floodfill/heuristic pass misses
    """

    name = "advanced"
    apiversion = "1"
    color = "#00ff00"
    author = "Skadoosh"

    # --- tunable weights (pull these out and tune via self-play logging) ---
    W_SURVIVAL = 100.0
    W_SPACE = 35.0
    W_FOOD_BASE = 18.0
    W_COLLISION = 55.0
    W_OFFENSE = 20.0
    W_LOOKAHEAD_TRAP = 40.0

    LOW_HEALTH_THRESHOLD = 50  # below this, food urgency starts ramping up
    STARVING_THRESHOLD = 20    # below this, food becomes near-mandatory
    HUNT_RANGE = 4             # manhattan distance within which we consider hunting

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        legal = legal_moves(game_state, you)
        if not legal:
            return "up"

        board = game_state["board"]
        width, height = board["width"], board["height"]
        head = parse_point(you["head"])
        your_len = int(you["length"])
        your_health = int(you.get("health", 100))
        foods = [parse_point(f) for f in board["food"]]
        hazards = {parse_point(h) for h in board.get("hazards", [])}

        blocked = self._blocked_cells(game_state, you)
        enemies = self._enemy_info(game_state, you)

        food_urgency = self._food_urgency(your_health)

        move_scores: dict[str, float] = {}

        for move in legal:
            nxt = next_position(head, move)
            sim_blocked = set(blocked)
            sim_blocked.discard(nxt)  # our head is about to occupy nxt, not "blocked"

            if nxt in blocked:
                move_scores[move] = -1e6  # never pick a cell we know kills us
                continue

            space = estimate_space(
                start=nxt,
                width=width,
                height=height,
                blocked=sim_blocked,
                limit=width * height,
            )
            space_score = space / (width * height)

            # single BFS call reused for both "can I reach food" and "how far"
            food_score = 0.0
            if foods:
                path = bfs_path(nxt, set(foods), width, height, sim_blocked)
                if path:
                    dist = max(1, len(path) - 1)
                    food_score = 1.0 / dist

            collision_risk = self._head_to_head_risk(nxt, enemies, your_len)
            offense_score = self._offense_score(nxt, enemies, your_len)
            trap_penalty = self._lookahead_trap_penalty(
                nxt, enemies, width, height, sim_blocked
            )
            hazard_penalty = 5.0 if nxt in hazards else 0.0

            move_scores[move] = (
                self.W_SURVIVAL
                + (self.W_SPACE * space_score)
                + (self.W_FOOD_BASE * food_urgency * food_score)
                + (self.W_OFFENSE * offense_score)
                - (self.W_COLLISION * collision_risk)
                - (self.W_LOOKAHEAD_TRAP * trap_penalty)
                - hazard_penalty
            )

        return max(move_scores, key=move_scores.get)

    # ------------------------------------------------------------------ #
    # Board state helpers
    # ------------------------------------------------------------------ #

    def _blocked_cells(self, game_state: dict[str, Any], you: dict[str, Any]) -> set[tuple[int, int]]:
        """
        Mark occupied cells. Tails that will vacate next turn (snake did not
        just eat) are excluded, since chasing an enemy's tail is usually safe
        and pure "block everything" logic wastes space unnecessarily.
        """
        blocked: set[tuple[int, int]] = set()
        for snake in game_state["board"]["snakes"]:
            if not snake.get("body"):
                continue

            body = [parse_point(p) for p in snake["body"]]

            if not body:
                continue

            just_ate = int(snake.get("health", 0)) == 100
            is_self = snake["id"] == you["id"]

            if len(body) > 1 and not just_ate:
                # tail cell will be empty next turn -> don't treat as blocked
                blocked.update(body[:-1])
            else:
                blocked.update(body)

            if is_self:
                # our own tail follows the same rule; nothing extra needed
                continue

        return blocked

    def _enemy_info(self, game_state: dict[str, Any], you: dict[str, Any]) -> list[dict[str, Any]]:
        out = []

        for snake in game_state["board"]["snakes"]:
            if snake["id"] == you["id"]:
                continue

            # Ignore dead snakes / incomplete data
            if not snake.get("body") or not snake.get("head"):
                continue

            out.append(
                {
                    "head": parse_point(snake["head"]),
                    "length": int(snake.get("length") or 0),
                    "health": int(snake.get("health") or 100),
                }
            )

        return out

    # ------------------------------------------------------------------ #
    # Scoring components
    # ------------------------------------------------------------------ #

    def _food_urgency(self, health: int) -> float:
        """
        0.0 when healthy (ignore food), ramping to >1.0 when starving so food
        weight actually dominates other terms when it matters.
        """
        if health >= self.LOW_HEALTH_THRESHOLD:
            return 0.15  # small baseline pull toward food even when healthy
        if health <= self.STARVING_THRESHOLD:
            return 2.0
        # linear ramp between thresholds
        span = self.LOW_HEALTH_THRESHOLD - self.STARVING_THRESHOLD
        progress = (self.LOW_HEALTH_THRESHOLD - health) / span
        return 0.15 + progress * (2.0 - 0.15)

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
        """
        Reward closing distance on strictly shorter enemies (a real kill
        threat we control), so the snake plays for eliminations when safe
        instead of only ever retreating.
        """
        best = 0.0
        for enemy in enemies:
            ehead, elen = enemy["head"], enemy["length"]
            if elen >= your_length:
                continue  # not a safe target, don't chase
            dist = abs(ehead[0] - target[0]) + abs(ehead[1] - target[1])
            if dist == 0:
                continue
            if dist <= self.HUNT_RANGE:
                best = max(best, 1.0 / dist)
        return best

    def _lookahead_trap_penalty(
        self,
        target: tuple[int, int],
        enemies: list[dict[str, Any]],
        width: int,
        height: int,
        blocked: set[tuple[int, int]],
    ) -> float:
        """
        Shallow 1-ply check: for nearby enemies, simulate their most
        aggressive plausible reply (moving toward our new head) and see how
        much space we'd have left afterward. Cheap trap detector that pure
        single-step floodfill misses (e.g. corridors that look open now but
        get sealed next turn).
        """
        nearby = [e for e in enemies if abs(e["head"][0] - target[0]) + abs(e["head"][1] - target[1]) <= 3]
        if not nearby:
            return 0.0

        worst_ratio = 1.0
        for enemy in nearby:
            ehead = enemy["head"]
            dx = target[0] - ehead[0]
            dy = target[1] - ehead[1]
            step = (
                ehead[0] + (1 if dx > 0 else -1 if dx < 0 else 0),
                ehead[1] + (1 if dy > 0 else -1 if dy < 0 else 0),
            )
            sim_blocked = set(blocked)
            sim_blocked.add(step)

            space_after = estimate_space(
                start=target,
                width=width,
                height=height,
                blocked=sim_blocked,
                limit=width * height,
            )
            ratio = space_after / (width * height)
            worst_ratio = min(worst_ratio, ratio)

        # low remaining space after worst-case enemy reply -> high penalty
        return max(0.0, 1.0 - worst_ratio)
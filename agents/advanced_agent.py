from __future__ import annotations

from typing import Any

from agent import BaseAgent, legal_moves, next_position, parse_point
from utils.floodfill import estimate_space
from utils.pathfinding import a_star_path, bfs_path


class AdvancedAgent(BaseAgent):
    name = "advanced"
    apiversion = "1"
    color = "#00ff00"
    author = "Skadoosh"

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        legal = legal_moves(game_state, you)
        if not legal:
            return "up"

        width = game_state["board"]["width"]
        height = game_state["board"]["height"]
        head = parse_point(you["head"])
        your_len = int(you["length"])
        your_health = int(you.get("health", 100))
        foods = [parse_point(food) for food in game_state["board"]["food"]]

        blocked = self._blocked_cells(game_state, you)
        enemy_heads = self._enemy_heads(game_state, you)
        move_scores: dict[str, float] = {}

        for move in legal:
            nxt = next_position(head, move)
            simulated_blocked = set(blocked)
            simulated_blocked.discard(nxt)

            survival_probability = 1.0
            if nxt in blocked:
                survival_probability = 0.0

            space = estimate_space(
                start=nxt,
                width=width,
                height=height,
                blocked=simulated_blocked,
                limit=width * height,
            )
            space_score = space / (width * height)

            food_score = 0.0
            if foods:
                path = bfs_path(nxt, set(foods), width, height, simulated_blocked)
                if path:
                    food_score = 1.0 / max(1, len(path) - 1)

                    if your_health > 70:
                        food_score *= 0.3
                    elif your_health < 30:
                        food_score *= 2.0
                        
            collision_risk = self._head_to_head_risk(
                target=nxt,
                enemy_heads=enemy_heads,
                your_length=your_len,
            )

            # a_star_bonus = 0.0
            # if foods:
            #     nearest_food = min(foods, key=lambda f: abs(nxt[0] - f[0]) + abs(nxt[1] - f[1]))
            #     if a_star_path(nxt, nearest_food, width, height, simulated_blocked):
            #         a_star_bonus = 0.15

            move_scores[move] = (
                (100.0 * survival_probability)
                + (50.0 * space_score)
                + (8.0 * food_score)
                - (55.0 * collision_risk)
            )

        return max(move_scores, key=move_scores.get)

    def _blocked_cells(self, game_state: dict[str, Any], you: dict[str, Any]) -> set[tuple[int, int]]:
        blocked: set[tuple[int, int]] = set()
        for snake in game_state["board"]["snakes"]:
            body = [parse_point(p) for p in snake["body"]]
            if not body:
                continue
            if snake["id"] == you["id"] and len(body) > 1:
                blocked.update(body[:-1])
            else:
                if len(body) > 1:
                    blocked.update(body[:-1])
                else:
                    blocked.update(body)

        return blocked

    def _enemy_heads(self, game_state: dict[str, Any], you: dict[str, Any]) -> list[tuple[tuple[int, int], int]]:
        out: list[tuple[tuple[int, int], int]] = []

        for snake in game_state["board"]["snakes"]:
            if snake["id"] == you["id"]:
                continue

            # Ignore dead snakes
            if not snake.get("head") or not snake.get("body"):
                continue

            out.append(
                (
                    parse_point(snake["head"]),
                    int(snake.get("length") or 0)
                )
            )

        return out

    def _head_to_head_risk(
        self,
        target: tuple[int, int],
        enemy_heads: list[tuple[tuple[int, int], int]],
        your_length: int,
        
    ) -> float:
        risk = 0.0
        for enemy_head, enemy_len in enemy_heads:
            dist = abs(enemy_head[0] - target[0]) + abs(enemy_head[1] - target[1])
            if dist == 1 and enemy_len >= your_length:
                risk = max(risk, 1.0)
            elif dist == 2 and enemy_len >= your_length:
                risk = max(risk, 0.4)
        return risk





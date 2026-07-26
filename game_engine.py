from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any

MOVE_DELTAS: dict[str, tuple[int, int]] = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass
class SnakeState:
    snake_id: str
    name: str
    body: list[tuple[int, int]]
    health: int = 100
    alive: bool = True
    death_turn: int | None = None
    death_reason: str | None = None

    @property
    def head(self) -> tuple[int, int]:
        return self.body[0]

    @property
    def length(self) -> int:
        return len(self.body)

    def as_public(self, body_override: list[tuple[int, int]] | None = None) -> dict[str, Any]:
        body = body_override if body_override is not None else self.body
        head = body[0] if body else self.head
        return {
            "id": self.snake_id,
            "name": self.name,
            "health": self.health,
            "body": [{"x": x, "y": y} for x, y in body],
            "head": {"x": head[0], "y": head[1]},
            "length": self.length,
        }


@dataclass
class TurnSnapshot:
    turn: int
    snakes: list[dict[str, Any]]
    food: list[dict[str, int]]
    width: int
    height: int


@dataclass
class BattlesnakeBlackoutEngine:
    width: int = 11
    height: int = 11
    vision_range: int = 5
    food_spawn_chance: float = 0.15
    min_food: int = 1
    max_turns: int = 500
    seed: int | None = None
    game_id: str = "local-blackout"
    snakes: dict[str, SnakeState] = field(default_factory=dict)
    turn: int = 0
    food: set[tuple[int, int]] = field(default_factory=set)
    food_spawn_turn: dict[tuple[int, int], int] = field(default_factory=dict)
    history: list[TurnSnapshot] = field(default_factory=list)
    elimination_events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)

    def add_snake(self, snake_id: str, name: str, start: tuple[int, int], length: int = 3) -> None:
        self.snakes[snake_id] = SnakeState(
            snake_id=snake_id,
            name=name,
            body=[start for _ in range(length)],
        )

    def initialize_four_snakes(self, snake_specs: list[tuple[str, str]]) -> None:
        if len(snake_specs) != 4:
            raise ValueError("Exactly 4 snakes are required.")
        spawns = [
            (1, 1),
            (self.width - 2, 1),
            (1, self.height - 2),
            (self.width - 2, self.height - 2),
        ]
        self.rng.shuffle(spawns)
        for (snake_id, name), spawn in zip(snake_specs, spawns, strict=True):
            self.add_snake(snake_id=snake_id, name=name, start=spawn)
        while len(self.food) < self.min_food:
            self._spawn_food(force=True)
        self._record_snapshot()

    def _in_bounds(self, p: tuple[int, int]) -> bool:
        return 0 <= p[0] < self.width and 0 <= p[1] < self.height

    def _random_empty_cell(self) -> tuple[int, int] | None:
        occupied = set(self.food)
        for snake in self.snakes.values():
            if snake.alive:
                occupied.update(snake.body)
        candidates = [
            (x, y)
            for x in range(self.width)
            for y in range(self.height)
            if (x, y) not in occupied
        ]
        if not candidates:
            return None
        return self.rng.choice(candidates)

    def _spawn_food(self, force: bool = False) -> None:
        if not force and self.rng.random() >= self.food_spawn_chance:
            return
        cell = self._random_empty_cell()
        if cell is None:
            return
        self.food.add(cell)
        self.food_spawn_turn[cell] = self.turn

    def _visible_cells(self, center: tuple[int, int]) -> set[tuple[int, int]]:
        visible: set[tuple[int, int]] = set()
        for x in range(self.width):
            for y in range(self.height):
                if manhattan(center, (x, y)) <= self.vision_range:
                    visible.add((x, y))
        return visible

    def get_observation(self, snake_id: str) -> dict[str, Any]:
        snake = self.snakes[snake_id]
        if not snake.alive:
            raise ValueError(f"Snake {snake_id} is dead.")

        visible = self._visible_cells(snake.head)
        board_snakes: list[dict[str, Any]] = []
        for other in self.snakes.values():
            if not other.alive:
                continue
            if other.snake_id == snake_id:
                board_snakes.append(other.as_public())
                continue
            visible_body = [segment for segment in other.body if segment in visible]
            if not visible_body:
                continue
            board_snakes.append(other.as_public(body_override=visible_body))

        visible_food = [
            {"x": x, "y": y}
            for (x, y) in self.food
            if self.food_spawn_turn.get((x, y)) == self.turn or (x, y) in visible
        ]
        you = snake.as_public()
        return {
            "game": {"id": self.game_id, "ruleset": {"name": "wrapped-blackout-local"}},
            "turn": self.turn,
            "board": {
                "height": self.height,
                "width": self.width,
                "food": visible_food,
                "hazards": [],
                "snakes": board_snakes,
            },
            "you": you,
        }

    def _record_snapshot(self) -> None:
        self.history.append(
            TurnSnapshot(
                turn=self.turn,
                snakes=[
                    snake.as_public()
                    for snake in self.snakes.values()
                    if snake.alive
                ],
                food=[{"x": x, "y": y} for x, y in self.food],
                width=self.width,
                height=self.height,
            )
        )

    def step(self, submitted_moves: dict[str, str]) -> None:
        if self.is_game_over():
            return

        alive_ids = [snake_id for snake_id, snake in self.snakes.items() if snake.alive]
        moves = {
            snake_id: submitted_moves.get(snake_id, "up")
            if submitted_moves.get(snake_id, "up") in MOVE_DELTAS
            else "up"
            for snake_id in alive_ids
        }
        new_heads = {
            snake_id: (
                self.snakes[snake_id].head[0] + MOVE_DELTAS[moves[snake_id]][0],
                self.snakes[snake_id].head[1] + MOVE_DELTAS[moves[snake_id]][1],
            )
            for snake_id in alive_ids
        }

        eaten = {snake_id for snake_id, head in new_heads.items() if head in self.food}

        for snake_id in alive_ids:
            snake = self.snakes[snake_id]
            snake.health -= 1
            snake.body = [new_heads[snake_id], *snake.body]
            if snake_id in eaten:
                snake.health = 100
                self.food.discard(new_heads[snake_id])
                self.food_spawn_turn.pop(new_heads[snake_id], None)
            else:
                snake.body.pop()

        dead: set[str] = set()
        death_reasons: dict[str, dict[str, Any]] = {}
        for snake_id in alive_ids:
            snake = self.snakes[snake_id]
            if not self._in_bounds(snake.head):
                dead.add(snake_id)
                death_reasons[snake_id] = {
                    "reason": "wall_collision",
                    "position": {"x": snake.head[0], "y": snake.head[1]},
                }
            elif snake.health <= 0:
                dead.add(snake_id)
                death_reasons[snake_id] = {
                    "reason": "starvation",
                    "position": {"x": snake.head[0], "y": snake.head[1]},
                }

        position_to_heads: dict[tuple[int, int], list[str]] = {}
        for snake_id in alive_ids:
            if snake_id in dead:
                continue
            position_to_heads.setdefault(self.snakes[snake_id].head, []).append(snake_id)
        for head_cell, contenders in position_to_heads.items():
            if len(contenders) < 2:
                continue
            max_len = max(self.snakes[sid].length for sid in contenders)
            longest = [sid for sid in contenders if self.snakes[sid].length == max_len]
            if len(longest) > 1:
                for sid in contenders:
                    dead.add(sid)
                    death_reasons[sid] = {
                        "reason": "head_to_head_tie",
                        "position": {"x": head_cell[0], "y": head_cell[1]},
                        "contenders": contenders,
                    }
            else:
                for sid in contenders:
                    if sid != longest[0]:
                        dead.add(sid)
                        death_reasons[sid] = {
                            "reason": "head_to_head_loss",
                            "position": {"x": head_cell[0], "y": head_cell[1]},
                            "winner": longest[0],
                            "contenders": contenders,
                        }

        occupied_body_cells: dict[tuple[int, int], list[str]] = {}
        for snake_id in alive_ids:
            body_without_head = self.snakes[snake_id].body[1:]
            for cell in body_without_head:
                occupied_body_cells.setdefault(cell, []).append(snake_id)
        for snake_id in alive_ids:
            if snake_id in dead:
                continue
            head = self.snakes[snake_id].head
            if head in occupied_body_cells:
                dead.add(snake_id)
                colliders = occupied_body_cells[head]
                reason = "snake_body_collision"
                if snake_id in colliders:
                    reason = "own_body_collision"
                death_reasons[snake_id] = {
                    "reason": reason,
                    "position": {"x": head[0], "y": head[1]},
                    "colliders": colliders,
                }

        for snake_id in dead:
            snake = self.snakes[snake_id]
            snake.alive = False
            snake.death_turn = self.turn
            snake.death_reason = death_reasons.get(snake_id, {}).get("reason", "unknown")
            self.elimination_events.append(
                {
                    "turn": self.turn,
                    "snake_id": snake_id,
                    "snake_name": snake.name,
                    "reason": snake.death_reason,
                    "details": death_reasons.get(snake_id, {}),
                }
            )

        if len(self.food) < self.min_food:
            self._spawn_food(force=True)
        else:
            self._spawn_food(force=False)

        self.turn += 1
        self._record_snapshot()

    def is_game_over(self) -> bool:
        alive = sum(1 for snake in self.snakes.values() if snake.alive)
        return alive <= 1 or self.turn >= self.max_turns

    def winner(self) -> str | None:
        alive = [snake_id for snake_id, snake in self.snakes.items() if snake.alive]
        return alive[0] if len(alive) == 1 else None

    def ranking(self) -> list[tuple[str, int]]:
        rank_data: list[tuple[str, int]] = []
        for snake_id, snake in self.snakes.items():
            survived_until = self.turn if snake.alive else (snake.death_turn or 0)
            rank_data.append((snake_id, survived_until))
        return sorted(rank_data, key=lambda item: item[1], reverse=True)

    def export_game_data(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "width": self.width,
            "height": self.height,
            "turns_played": self.turn,
            "winner": self.winner(),
            "ranking": self.ranking(),
            "snakes": [
                {
                    "id": snake.snake_id,
                    "name": snake.name,
                    "alive": snake.alive,
                    "length": snake.length,
                    "health": snake.health,
                    "death_turn": snake.death_turn,
                    "death_reason": snake.death_reason,
                }
                for snake in self.snakes.values()
            ],
            "eliminations": self.elimination_events,
            "history": [
                {
                    "turn": snap.turn,
                    "snakes": snap.snakes,
                    "food": snap.food,
                    "width": snap.width,
                    "height": snap.height,
                }
                for snap in self.history
            ],
        }

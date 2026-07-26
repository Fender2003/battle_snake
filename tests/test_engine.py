import json
from pathlib import Path

from game_engine import BattlesnakeBlackoutEngine
from utils.game_logger import GameLogger, summarize_losses


def test_head_to_head_equal_length_both_die() -> None:
    engine = BattlesnakeBlackoutEngine(width=7, height=7, seed=1)
    engine.add_snake("a", "a", (2, 3), length=3)
    engine.add_snake("b", "b", (4, 3), length=3)
    engine.step({"a": "right", "b": "left"})
    assert not engine.snakes["a"].alive
    assert not engine.snakes["b"].alive


def test_blackout_hides_distant_enemy() -> None:
    engine = BattlesnakeBlackoutEngine(width=11, height=11, vision_range=2, seed=1)
    engine.add_snake("a", "a", (1, 1), length=3)
    engine.add_snake("b", "b", (9, 9), length=3)
    obs = engine.get_observation("a")
    snake_ids = {s["id"] for s in obs["board"]["snakes"]}
    assert "a" in snake_ids
    assert "b" not in snake_ids


def test_food_global_visibility_on_spawn_turn() -> None:
    engine = BattlesnakeBlackoutEngine(width=11, height=11, vision_range=1, seed=3)
    engine.add_snake("a", "a", (1, 1), length=3)
    engine.add_snake("b", "b", (9, 9), length=3)
    engine.food = {(8, 8)}
    engine.food_spawn_turn = {(8, 8): 0}
    obs_turn_0 = engine.get_observation("a")
    assert {"x": 8, "y": 8} in obs_turn_0["board"]["food"]

    engine.step({"a": "up", "b": "down"})
    obs_turn_1 = engine.get_observation("a")
    assert {"x": 8, "y": 8} not in obs_turn_1["board"]["food"]


def test_wall_collision_has_death_reason() -> None:
    engine = BattlesnakeBlackoutEngine(width=5, height=5, seed=2)
    engine.add_snake("a", "a", (0, 0), length=3)
    engine.add_snake("b", "b", (4, 4), length=3)
    engine.step({"a": "left", "b": "down"})
    assert not engine.snakes["a"].alive
    assert engine.snakes["a"].death_reason == "wall_collision"


def test_game_logger_writes_and_summarizes(tmp_path: Path) -> None:
    engine = BattlesnakeBlackoutEngine(width=5, height=5, seed=4)
    engine.add_snake("my-advanced", "my-advanced", (0, 0), length=3)
    engine.add_snake("b", "b", (4, 4), length=3)
    engine.step({"my-advanced": "left", "b": "down"})
    logger = GameLogger(tmp_path)
    file_path = logger.log_game(
        engine,
        game_label="test",
        my_snake_id="my-advanced",
        agent_map={"my-advanced": "advanced", "b": "random"},
    )
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    assert payload["snakes"][0]["id"] == "my-advanced"
    summary = summarize_losses(tmp_path, "my-advanced")
    assert summary["total_games_logged"] == 1
    assert summary["death_reason_counts"]["wall_collision"] == 1

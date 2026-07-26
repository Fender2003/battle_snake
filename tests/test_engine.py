from game_engine import BattlesnakeBlackoutEngine


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

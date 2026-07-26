from __future__ import annotations

import argparse

from agent import BaseAgent
from agents.advanced_agent import AdvancedAgent
from agents.greedy_food_agent import GreedyFoodAgent
from agents.random_agent import RandomAgent
from game_engine import BattlesnakeBlackoutEngine
from utils.visualization import replay_game


def run_local_game(max_turns: int, seed: int | None, visualize: bool) -> None:
    engine = BattlesnakeBlackoutEngine(max_turns=max_turns, seed=seed)
    agents: dict[str, BaseAgent] = {
        "my-advanced": AdvancedAgent(),
        "greedy-1": GreedyFoodAgent(),
        "random-1": RandomAgent(),
        "random-2": RandomAgent(),
    }
    engine.initialize_four_snakes([(snake_id, snake_id) for snake_id in agents])

    while not engine.is_game_over():
        moves: dict[str, str] = {}
        for snake_id, snake in engine.snakes.items():
            if not snake.alive:
                continue
            obs = engine.get_observation(snake_id)
            moves[snake_id] = agents[snake_id].move(obs, obs["you"])
        engine.step(moves)

    winner = engine.winner()
    print(f"Game finished at turn {engine.turn}.")
    print("Winner:", winner or "None (draw)")
    print("Ranking:", engine.ranking())

    if visualize:
        replay_game(engine.history, pause_seconds=0.18)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local Battlesnake Blackout game.")
    parser.add_argument("--max-turns", type=int, default=400)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--visualize", action="store_true")
    args = parser.parse_args()
    run_local_game(max_turns=args.max_turns, seed=args.seed, visualize=args.visualize)


if __name__ == "__main__":
    main()

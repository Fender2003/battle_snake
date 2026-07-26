from __future__ import annotations

import argparse
from pathlib import Path

from agent import BaseAgent
from agents.advanced_agent import AdvancedAgent
from agents.greedy_food_agent import GreedyFoodAgent
from agents.random_agent import RandomAgent
from game_engine import BattlesnakeBlackoutEngine
from utils.game_logger import GameLogger
from utils.visualization import replay_game


def run_local_game(
    max_turns: int,
    seed: int | None,
    visualize: bool,
    log_dir: Path,
    save_log: bool,
) -> None:
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
    if save_log:
        logger = GameLogger(log_dir)
        log_path = logger.log_game(
            engine,
            game_label=f"single_seed_{seed if seed is not None else 'none'}",
            my_snake_id="my-advanced",
            agent_map={snake_id: agents[snake_id].name for snake_id in agents},
        )
        my_result = engine.snakes["my-advanced"]
        if winner == "my-advanced":
            print(f"My snake won. Log saved at: {log_path}")
        elif my_result.alive:
            print(f"My snake survived (no winner). Log saved at: {log_path}")
        else:
            print(
                "My snake lost:",
                my_result.death_reason or "unknown",
                f"(turn {my_result.death_turn})",
            )
            print(f"Log saved at: {log_path}")

    if visualize:
        replay_game(engine.history, pause_seconds=0.18)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local Battlesnake Blackout game.")
    parser.add_argument("--max-turns", type=int, default=400)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--visualize", action="store_true")
    parser.add_argument("--log-dir", type=Path, default=Path("logs/games"))
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args()
    run_local_game(
        max_turns=args.max_turns,
        seed=args.seed,
        visualize=args.visualize,
        log_dir=args.log_dir,
        save_log=not args.no_log,
    )


if __name__ == "__main__":
    main()

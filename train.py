from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from agent import BaseAgent
from agents.advanced_agent import AdvancedAgent
from agents.greedy_food_agent import GreedyFoodAgent
from agents.random_agent import RandomAgent
from game_engine import BattlesnakeBlackoutEngine
from utils.game_logger import GameLogger, summarize_losses


def run_self_play(games: int, max_turns: int, output: Path, log_dir: Path) -> None:
    my_id = "my-advanced"
    wins = 0
    survival_turns: list[int] = []
    ranks: list[int] = []
    logger = GameLogger(log_dir)

    for game_index in range(games):
        engine = BattlesnakeBlackoutEngine(max_turns=max_turns, seed=game_index)
        agents: dict[str, BaseAgent] = {
            my_id: AdvancedAgent(),
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
        if winner == my_id:
            wins += 1

        my_snake = engine.snakes[my_id]
        survival_turns.append(engine.turn if my_snake.alive else (my_snake.death_turn or 0))

        rank_order = [snake_id for snake_id, _ in engine.ranking()]
        ranks.append(rank_order.index(my_id) + 1)
        logger.log_game(
            engine,
            game_label=f"selfplay_{game_index:05d}",
            my_snake_id=my_id,
            agent_map={snake_id: agents[snake_id].name for snake_id in agents},
        )

    report = {
        "games": games,
        "wins": wins,
        "win_rate": wins / games if games else 0.0,
        "average_survival_turns": mean(survival_turns) if survival_turns else 0.0,
        "average_rank": mean(ranks) if ranks else 0.0,
    }
    report["loss_analysis"] = summarize_losses(log_dir, my_id)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Self-play training simulation.")
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--max-turns", type=int, default=400)
    parser.add_argument("--output", type=Path, default=Path("self_play_results.json"))
    parser.add_argument("--log-dir", type=Path, default=Path("logs/games"))
    args = parser.parse_args()
    run_self_play(games=args.games, max_turns=args.max_turns, output=args.output, log_dir=args.log_dir)


if __name__ == "__main__":
    main()

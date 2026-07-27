# from __future__ import annotations

# import argparse
# import json
# from pathlib import Path
# from statistics import mean

# from agent import BaseAgent
# from agents.advanced_agent import AdvancedAgent
# from agents.greedy_food_agent import GreedyFoodAgent
# from agents.random_agent import RandomAgent
# from game_engine import BattlesnakeBlackoutEngine
# from utils.game_logger import GameLogger, summarize_losses


# def run_self_play(games: int, max_turns: int, output: Path, log_dir: Path) -> None:
#     my_id = "my-advanced"
#     wins = 0
#     survival_turns: list[int] = []
#     ranks: list[int] = []
#     logger = GameLogger(log_dir)

#     for game_index in range(games):
#         engine = BattlesnakeBlackoutEngine(max_turns=max_turns, seed=game_index)
#         agents: dict[str, BaseAgent] = {
#             my_id: AdvancedAgent(),
#             "advanced-1": AdvancedAgent(),
#             "advanced-2": AdvancedAgent(),
#             "advanced-3": AdvancedAgent(),
#         }
#         engine.initialize_four_snakes([(snake_id, snake_id) for snake_id in agents])

#         while not engine.is_game_over():
#             moves: dict[str, str] = {}
#             for snake_id, snake in engine.snakes.items():
#                 if not snake.alive:
#                     continue
#                 obs = engine.get_observation(snake_id)
#                 moves[snake_id] = agents[snake_id].move(obs, obs["you"])
#             engine.step(moves)

#         winner = engine.winner()
#         if winner == my_id:
#             wins += 1

#         my_snake = engine.snakes[my_id]
#         survival_turns.append(engine.turn if my_snake.alive else (my_snake.death_turn or 0))

#         rank_order = [snake_id for snake_id, _ in engine.ranking()]
#         ranks.append(rank_order.index(my_id) + 1)
#         logger.log_game(
#             engine,
#             game_label=f"selfplay_{game_index:05d}",
#             my_snake_id=my_id,
#             agent_map={snake_id: agents[snake_id].name for snake_id in agents},
#         )

#     report = {
#         "games": games,
#         "wins": wins,
#         "win_rate": wins / games if games else 0.0,
#         "average_survival_turns": mean(survival_turns) if survival_turns else 0.0,
#         "average_rank": mean(ranks) if ranks else 0.0,
#     }
#     report["loss_analysis"] = summarize_losses(log_dir, my_id)
#     output.write_text(json.dumps(report, indent=2), encoding="utf-8")
#     print(json.dumps(report, indent=2))


# def main() -> None:
#     parser = argparse.ArgumentParser(description="Self-play training simulation.")
#     parser.add_argument("--games", type=int, default=1000)
#     parser.add_argument("--max-turns", type=int, default=400)
#     parser.add_argument("--output", type=Path, default=Path("self_play_results.json"))
#     parser.add_argument("--log-dir", type=Path, default=Path("logs/games"))
#     args = parser.parse_args()
#     run_self_play(games=args.games, max_turns=args.max_turns, output=args.output, log_dir=args.log_dir)


# if __name__ == "__main__":
#     main()
# test_against_strong.py

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from agent import BaseAgent
from agents.advanced_agent import AdvancedAgent
from agents.minimax_agent import MinimaxAgent
from agents.aggressive_agent import AggressiveAgent
from agents.defensive_agent import DefensiveAgent
from agents.greedy_food_agent import GreedyFoodAgent
from game_engine import BattlesnakeBlackoutEngine
from utils.game_logger import GameLogger


def run_test(games: int, max_turns: int, output: Path, log_dir: Path) -> None:
    my_id = "my-advanced"
    
    # Test against different opponent types
    test_configs = [
        ("vs_minimax", [MinimaxAgent, MinimaxAgent, MinimaxAgent]),
        ("vs_aggressive", [AggressiveAgent, AggressiveAgent, AggressiveAgent]),
        ("vs_defensive", [DefensiveAgent, DefensiveAgent, DefensiveAgent]),
        ("vs_greedy", [GreedyFoodAgent, GreedyFoodAgent, GreedyFoodAgent]),
        ("vs_mixed", [MinimaxAgent, AggressiveAgent, DefensiveAgent]),
    ]
    
    all_results = {}
    
    for config_name, opponent_classes in test_configs:
        print(f"\n=== Testing {config_name} ===")
        wins = 0
        survival_turns = []
        ranks = []
        
        logger = GameLogger(log_dir / config_name)
        
        for game_index in range(games):
            engine = BattlesnakeBlackoutEngine(max_turns=max_turns, seed=game_index)
            agents = {my_id: AdvancedAgent()}
            for i, opp_class in enumerate(opponent_classes):
                agents[f"opp-{i}"] = opp_class()
            
            engine.initialize_four_snakes([(sid, sid) for sid in agents])
            
            while not engine.is_game_over():
                moves = {}
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
            
            rank_order = [sid for sid, _ in engine.ranking()]
            ranks.append(rank_order.index(my_id) + 1)
        
        results = {
            "games": games,
            "wins": wins,
            "win_rate": wins / games if games else 0.0,
            "avg_survival": mean(survival_turns) if survival_turns else 0.0,
            "avg_rank": mean(ranks) if ranks else 0.0,
        }
        all_results[config_name] = results
        print(json.dumps(results, indent=2))
    
    output.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\n=== Summary ===")
    print(json.dumps(all_results, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--max-turns", type=int, default=400)
    parser.add_argument("--output", type=Path, default=Path("test_results.json"))
    parser.add_argument("--log-dir", type=Path, default=Path("logs/tests"))
    args = parser.parse_args()
    run_test(args.games, args.max_turns, args.output, args.log_dir)


if __name__ == "__main__":
    main()
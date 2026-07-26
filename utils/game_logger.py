from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from game_engine import BattlesnakeBlackoutEngine


class GameLogger:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_game(
        self,
        engine: BattlesnakeBlackoutEngine,
        *,
        game_label: str,
        my_snake_id: str,
        agent_map: dict[str, str],
    ) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        file_path = self.log_dir / f"{timestamp}_{game_label}.json"
        data = engine.export_game_data()
        my_snake = next((snake for snake in data["snakes"] if snake["id"] == my_snake_id), None)
        data["log_metadata"] = {
            "saved_at_utc": timestamp,
            "game_label": game_label,
            "my_snake_id": my_snake_id,
            "my_snake_result": my_snake,
            "agent_map": agent_map,
        }
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return file_path


def summarize_losses(log_dir: Path, my_snake_id: str) -> dict[str, Any]:
    files = sorted(log_dir.glob("*.json"))
    death_reasons: Counter[str] = Counter()
    by_reason_turns: dict[str, list[int]] = defaultdict(list)
    total_games = 0
    wins = 0

    for file_path in files:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        total_games += 1
        if payload.get("winner") == my_snake_id:
            wins += 1
        snake_entries = payload.get("snakes", [])
        my_entry = next((s for s in snake_entries if s.get("id") == my_snake_id), None)
        if not my_entry:
            continue
        reason = my_entry.get("death_reason")
        if reason:
            death_reasons[reason] += 1
            turn = my_entry.get("death_turn")
            if isinstance(turn, int):
                by_reason_turns[reason].append(turn)

    avg_turn_by_reason = {
        reason: sum(turns) / len(turns) for reason, turns in by_reason_turns.items() if turns
    }
    return {
        "total_games_logged": total_games,
        "wins": wins,
        "losses": max(total_games - wins, 0),
        "death_reason_counts": dict(death_reasons),
        "avg_death_turn_by_reason": avg_turn_by_reason,
    }

# Battlesnake Blackout Local Environment

Local Python 3.11+ environment for testing Battlesnake agents with a realistic Blackout (fog-of-war) simulator, API server, self-play, and visualization.

## Features

- 4-snake simultaneous turn simulator.
- Core rules: health drain, food growth, wall/body/head-to-head collisions.
- Blackout visibility:
  - Vision radius = 5 tiles from each snake head.
  - Hidden enemy snakes are removed from that snake's observation.
  - Food is globally visible only on the turn it spawns; afterward it follows visibility.
- Battlesnake-compatible API endpoints (`/`, `/start`, `/move`, `/end`).
- Modular agent system (`random`, `greedy`, `advanced`).
- Self-play benchmarking with JSON output.
- Matplotlib local visualization replay.
- Docker + Render/Railway deploy config.

## Project Structure

```text
project/
├── server.py
├── game_engine.py
├── agent.py
├── run_game.py
├── train.py
├── agents/
│   ├── random_agent.py
│   ├── greedy_food_agent.py
│   └── advanced_agent.py
├── utils/
│   ├── pathfinding.py
│   ├── floodfill.py
│   └── visualization.py
└── tests/
```

## Installation

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Local Tournament Game

```bash
python run_game.py --visualize
```

Options:
- `--max-turns 400`
- `--seed 123`
- `--visualize` (replay with matplotlib)

## Run Self-Play Training

```bash
python train.py --games 2000 --output self_play_results.json
```

Outputs:
- wins
- win rate
- average survival turns
- average rank

## Run API Server

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Set active agent:

```bash
SNAKE_AGENT=advanced uvicorn server:app --host 0.0.0.0 --port 8000
```

Available:
- `advanced`
- `greedy`
- `random`

## Replace AI Logic

- Implement a new class extending `BaseAgent` in `agents/`.
- Add it to `build_agent()` in `agent.py`.
- Set `SNAKE_AGENT=<your_agent_name>` before launching `server.py`.

## Deploy (Render / Railway)

### Render
1. Push repo to GitHub.
2. Create a new Render Web Service.
3. Use `render.yaml` (Docker free plan).
4. Set env vars if needed (`SNAKE_AGENT=advanced`).

### Railway
1. Connect GitHub repo.
2. Railway uses `railway.json` and Dockerfile.
3. Service starts with `uvicorn server:app --host 0.0.0.0 --port $PORT`.

## Performance Notes

- Keep `POST /move` deterministic and lightweight.
- Precompute board features where possible.
- This code path is designed for sub-500ms responses under typical board sizes.

## Tests

```bash
pytest -q
```

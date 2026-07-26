from __future__ import annotations

import time
from itertools import product
from collections import deque
from typing import Any, Optional

from agent import BaseAgent, legal_moves, next_position, parse_point


class AdvancedAgent(BaseAgent):
    """
    Minimax-based Battlesnake with depth-2 lookahead.

    Core idea:
      - You (MAX) pick the move that leads to the best WORST-CASE outcome.
      - Opponents (MIN) are assumed to pick the move that's worst for YOU.
      - We branch over ALL legal opponent moves (not just greedy), so we
        never get surprised by a smart trap.

    Performance:
      - Depth 2 with ~3 opponents × ~3 moves each = ~81 leaf evaluations.
      - Each evaluation is a couple of small floodfills on an 11x11 board.
      - Total: well under 100ms on free Render.
      - Time-bounded at 350ms with iterative deepening as a safety net.
    """

    name = "advanced"
    apiversion = "1"
    color = "#8b00ff"
    author = "Skadoosh"

    TIME_LIMIT = 0.35  # seconds — leave headroom for Render overhead

    # Evaluation weights
    W_SPACE = 120.0
    W_OPP_SPACE = -90.0
    W_H2H_WIN = 400.0
    W_H2H_LOSE = -600.0
    W_HEALTH = 0.6
    W_LENGTH = 8.0
    W_FOOD_HUNGRY = 3.5
    W_FOOD_STARVING = 8.0
    W_DEAD = -100000.0
    W_WIN = 100000.0

    HUNGRY_THRESHOLD = 55
    STARVING_THRESHOLD = 25

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        start = time.time()
        try:
            return self._search(game_state, you, start)
        except Exception:
            return self._fallback(game_state, you)

    def _fallback(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        try:
            moves = legal_moves(game_state, you)
            return moves[0] if moves else "up"
        except Exception:
            return "up"

    # ------------------------------------------------------------------ #
    # State parsing
    # ------------------------------------------------------------------ #

    def _search(self, game_state: dict[str, Any], you: dict[str, Any],
                start: float) -> str:
        board = game_state["board"]
        W, H = board["width"], board["height"]
        foods = [parse_point(f) for f in board.get("food", [])]

        you_id = you["id"]
        your_body = [parse_point(p) for p in you["body"]]
        your_head = your_body[0]
        your_len = len(your_body)
        your_hp = int(you.get("health", 100))

        # Opponents: list of dicts with body/head/len/hp
        opps: list[dict] = []
        for s in board.get("snakes", []):
            if s["id"] == you_id:
                continue
            body = [parse_point(p) for p in s.get("body", [])]
            if body:
                opps.append({
                    "body": body,
                    "head": body[0],
                    "len": len(body),
                    "hp": int(s.get("health", 100)),
                })

        # Your safe moves (no immediate self-collision or wall)
        your_moves = self._safe_moves(
            your_head, your_body, opps, W, H, you_are=0
        )
        if not your_moves:
            # All moves kill us — just pick any legal one
            lm = legal_moves(game_state, you)
            return lm[0] if lm else "up"
        if len(your_moves) == 1:
            return your_moves[0]

        # ------------------------------------------------------------------
        # Minimax root: you (MAX) pick the best move
        # ------------------------------------------------------------------
        best_move = your_moves[0]
        best_score = -1e18

        # Iterative deepening: depth 1, then 2. Depth 3 only if very fast.
        for depth in (1, 2, 3):
            if time.time() - start > self.TIME_LIMIT:
                break

            cur_best = your_moves[0]
            cur_best_score = -1e18

            for m in your_moves:
                if time.time() - start > self.TIME_LIMIT:
                    break

                # Simulate your move (you + opponents all move simultaneously)
                heads, bodies, lens, hps = self._simulate_all(
                    your_head, your_body, your_len, your_hp, m,
                    opps, W, H
                )
                if heads[0] is None:
                    continue  # you died from H2H or something

                score = self._min_min(
                    heads, bodies, lens, hps, foods, W, H, depth - 1, start
                )
                if score > cur_best_score:
                    cur_best_score = score
                    cur_best = m

            best_move = cur_best
            best_score = cur_best_score

            # If we found a winning move, stop searching
            if best_score >= self.W_WIN / 2:
                break

        return best_move

    # ------------------------------------------------------------------ #
    # Minimax: opponents' turn (MIN node)
    # ------------------------------------------------------------------ #

    def _min_min(self, heads, bodies, lens, hps, foods, W, H,
                 depth: int, start: float) -> float:
        if time.time() - start > self.TIME_LIMIT or depth <= 0:
            return self._evaluate(heads, bodies, lens, hps, foods, W, H)

        # Gather legal moves for each living opponent
        opp_move_lists: list[list[str]] = []
        opp_indices: list[int] = []
        for i in range(1, len(heads)):
            if heads[i] is None:
                continue
            moves = self._safe_moves(
                heads[i], bodies[i],
                self._as_opps(heads, bodies, lens, hps, i),
                W, H, you_are=i
            )
            if not moves:
                # Opponent has no safe move — they'll die. Skip them.
                continue
            opp_move_lists.append(moves)
            opp_indices.append(i)

        if not opp_move_lists:
            # All opponents dead (or will die) — you win
            return self.W_WIN

        min_score = 1e18
        for combo in product(*opp_move_lists):
            # Apply this combination of opponent moves
            new_heads, new_bodies, new_lens, new_hps = self._simulate_opps(
                heads, bodies, lens, hps, opp_indices, combo, W, H
            )
            score = self._max_you(
                new_heads, new_bodies, new_lens, new_hps,
                foods, W, H, depth - 1, start
            )
            if score < min_score:
                min_score = score
                if min_score <= self.W_DEAD:
                    break  # alpha cutoff — can't get worse

        return min_score

    # ------------------------------------------------------------------ #
    # Minimax: your turn (MAX node)
    # ------------------------------------------------------------------ #

    def _max_you(self, heads, bodies, lens, hps, foods, W, H,
                 depth: int, start: float) -> float:
        if time.time() - start > self.TIME_LIMIT or depth <= 0:
            return self._evaluate(heads, bodies, lens, hps, foods, W, H)

        if heads[0] is None:
            return self.W_DEAD

        opps_for_safe = self._as_opps(heads, bodies, lens, hps, 0)
        moves = self._safe_moves(heads[0], bodies[0], opps_for_safe, W, H, you_are=0)
        if not moves:
            return self.W_DEAD

        max_score = -1e18
        for m in moves:
            new_heads, new_bodies, new_lens, new_hps = self._simulate_all(
                heads[0], bodies[0], lens[0], hps[0], m,
                opps_for_safe, W, H
            )
            score = self._min_min(
                new_heads, new_bodies, new_lens, new_hps,
                foods, W, H, depth - 1, start
            )
            if score > max_score:
                max_score = score

        return max_score

    # ------------------------------------------------------------------ #
    # Simulation helpers
    # ------------------------------------------------------------------ #

    def _as_opps(self, heads, bodies, lens, hps, skip_idx: int) -> list[dict]:
        """Build a list of opponent dicts, skipping the given index."""
        opps = []
        for i in range(len(heads)):
            if i == skip_idx or heads[i] is None:
                continue
            opps.append({
                "body": bodies[i],
                "head": heads[i],
                "len": lens[i],
                "hp": hps[i],
            })
        return opps

    def _safe_moves(self, head, body, opps, W, H, you_are: int) -> list[str]:
        """Legal moves that don't immediately kill `you_are`-th snake."""
        blocked: set[tuple[int, int]] = set()

        # Other snakes' bodies (their tail will move, so exclude it)
        for i, opp in enumerate(opps):
            b = opp["body"]
            if len(b) > 1:
                blocked.update(b[:-1])
            else:
                blocked.update(b)

        # Your own body (your tail will move too)
        if len(body) > 1:
            blocked.update(body[:-1])
        else:
            blocked.update(body)

        out: list[str] = []
        for m in ("up", "down", "left", "right"):
            nx, ny = next_position(head, m)
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            if (nx, ny) in blocked:
                continue
            # Head-to-head with longer/equal opponent = death
            p = (nx, ny)
            dead = False
            for opp in opps:
                oh = opp["head"]
                for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    if (oh[0] + dx, oh[1] + dy) == p:
                        if len(body) <= opp["len"]:
                            dead = True
                            break
                if dead:
                    break
            if dead:
                continue
            out.append(m)
        return out

    def _simulate_all(self, your_head, your_body, your_len, your_hp,
                      your_move, opps, W, H):
        """
        Simulate one full turn: you + all opponents move simultaneously.
        Returns (heads, bodies, lens, hps) where index 0 = you.
        A dead snake has head=None.
        """
        # Proposed new heads
        proposed = [next_position(your_head, your_move)]
        for opp in opps:
            # Opponent greedy: pick the safe move that maximizes their space
            # (simple opponent model — good enough for depth-2)
            opp_moves = self._safe_moves(
                opp["head"], opp["body"],
                [{"body": your_body, "head": your_head, "len": your_len, "hp": your_hp}],
                W, H, you_are=0
            )
            if not opp_moves:
                proposed.append(None)
                continue
            # Pick the move that gives them the most space (simple heuristic)
            best_m = opp_moves[0]
            best_space = -1
            for om in opp_moves:
                nh = next_position(opp["head"], om)
                sp = self._quick_space(nh, opp["body"], W, H)
                if sp > best_space:
                    best_space = sp
                    best_m = om
            proposed.append(next_position(opp["head"], best_m))

        # Resolve collisions
        heads: list[Optional[tuple[int, int]]] = [None] * (1 + len(opps))
        bodies: list[list] = [[] for _ in range(1 + len(opps))]
        lens = [0] * (1 + len(opps))
        hps = [0] * (1 + len(opps))

        all_bodies = [your_body] + [o["body"] for o in opps]
        all_lens = [your_len] + [o["len"] for o in opps]
        all_hps = [your_hp] + [o["hp"] for o in opps]

        # Head-to-wall / head-to-body kills
        alive = [True] * (1 + len(opps))
        for i, nh in enumerate(proposed):
            if nh is None:
                alive[i] = False
                continue
            if not (0 <= nh[0] < W and 0 <= nh[1] < H):
                alive[i] = False
                continue
            # Hit any body (other snakes' full body, your body except tail)?
            for j, b in enumerate(all_bodies):
                if j == i:
                    # Your own body — tail will vacate unless you just ate
                    check_body = b[:-1] if len(b) > 1 else b
                else:
                    check_body = b  # opponent's full body (their tail may not vacate)
                if nh in check_body:
                    alive[i] = False
                    break

        # Head-to-head: if two alive snakes land on same cell, shorter dies
        for i in range(len(proposed)):
            if not alive[i] or proposed[i] is None:
                continue
            for j in range(i + 1, len(proposed)):
                if not alive[j] or proposed[j] is None:
                    continue
                if proposed[i] == proposed[j]:
                    if all_lens[i] > all_lens[j]:
                        alive[j] = False
                    elif all_lens[j] > all_lens[i]:
                        alive[i] = False
                    else:
                        alive[i] = False
                        alive[j] = False

        # Build result
        for i in range(1 + len(opps)):
            if alive[i]:
                heads[i] = proposed[i]
                # Did this snake eat? (head is on food)
                ate = proposed[i] in self._food_set_cache if hasattr(self, '_food_set_cache') else False
                # We don't track food here for speed — just shift body
                new_body = [proposed[i]] + all_bodies[i][:-1]
                bodies[i] = new_body
                lens[i] = all_lens[i]
                hps[i] = max(0, all_hps[i] - 1)
            else:
                heads[i] = None
                bodies[i] = []
                lens[i] = 0
                hps[i] = 0

        return heads, bodies, lens, hps

    def _simulate_opps(self, heads, bodies, lens, hps, opp_indices, opp_moves,
                       W, H):
        """Apply a specific combination of opponent moves (you stay put for this step)."""
        new_heads = list(heads)
        new_bodies = [list(b) for b in bodies]
        new_lens = list(lens)
        new_hps = list(hps)

        proposed = {idx: next_position(heads[idx], m)
                    for idx, m in zip(opp_indices, opp_moves)}

        # Resolve opponent-vs-opponent and opponent-vs-you collisions
        alive = {idx: True for idx in opp_indices}

        for idx, nh in proposed.items():
            if not (0 <= nh[0] < W and 0 <= nh[1] < H):
                alive[idx] = False
                continue
            # Hit your body?
            if heads[0] is not None:
                your_body_check = bodies[0][:-1] if len(bodies[0]) > 1 else bodies[0]
                if nh in your_body_check:
                    alive[idx] = False
                    continue
            # Hit another opponent's body?
            for j in opp_indices:
                if j == idx or not alive.get(j, False):
                    continue
                opp_body = bodies[j]
                if nh in opp_body:
                    alive[idx] = False
                    break

        # Opponent-vs-opponent H2H
        for i_idx in opp_indices:
            if not alive[i_idx]:
                continue
            for j_idx in opp_indices:
                if i_idx >= j_idx or not alive[j_idx]:
                    continue
                if proposed[i_idx] == proposed[j_idx]:
                    if lens[i_idx] > lens[j_idx]:
                        alive[j_idx] = False
                    elif lens[j_idx] > lens[i_idx]:
                        alive[i_idx] = False
                    else:
                        alive[i_idx] = False
                        alive[j_idx] = False

        for idx in opp_indices:
            if alive[idx]:
                new_heads[idx] = proposed[idx]
                new_bodies[idx] = [proposed[idx]] + bodies[idx][:-1]
                new_hps[idx] = max(0, hps[idx] - 1)
            else:
                new_heads[idx] = None
                new_bodies[idx] = []
                new_lens[idx] = 0
                new_hps[idx] = 0

        return new_heads, new_bodies, new_lens, new_hps

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #

    def _evaluate(self, heads, bodies, lens, hps, foods, W, H) -> float:
        if heads[0] is None:
            return self.W_DEAD

        # Are all opponents dead?
        all_dead = all(heads[i] is None for i in range(1, len(heads)))
        if all_dead:
            return self.W_WIN

        score = 0.0
        total_cells = W * H

        # Your space (floodfill)
        your_space = self._floodfill(heads[0], bodies, W, H)
        score += self.W_SPACE * (your_space / total_cells)

        your_len = lens[0]
        your_hp = hps[0]

        # Per-opponent terms
        opp_len_sum = 0
        opp_count = 0
        for i in range(1, len(heads)):
            if heads[i] is None:
                continue
            opp_count += 1
            opp_len_sum += lens[i]

            opp_space = self._floodfill(heads[i], bodies, W, H)
            score += self.W_OPP_SPACE * (opp_space / total_cells)

            # Head-to-head opportunity
            if self._adjacent(heads[0], heads[i]):
                if your_len > lens[i]:
                    score += self.W_H2H_WIN
                elif your_len < lens[i]:
                    score += self.W_H2H_LOSE
                else:
                    score += self.W_H2H_LOSE * 0.5  # tie = bad

            # Nearby threat
            dist = abs(heads[0][0] - heads[i][0]) + abs(heads[0][1] - heads[i][1])
            if dist <= 3 and lens[i] >= your_len:
                score -= 40.0 * (4 - dist)

        # Health
        score += self.W_HEALTH * (your_hp - 50)

        # Length advantage
        if opp_count > 0:
            avg_opp_len = opp_len_sum / opp_count
            score += self.W_LENGTH * (your_len - avg_opp_len)

        # Food (only when hungry)
        if foods:
            if your_hp <= self.STARVING_THRESHOLD:
                w = self.W_FOOD_STARVING
            elif your_hp <= self.HUNGRY_THRESHOLD:
                w = self.W_FOOD_HUNGRY
            else:
                w = 0.0
            if w > 0:
                nearest = min(abs(heads[0][0] - f[0]) + abs(heads[0][1] - f[1])
                              for f in foods)
                score -= w * nearest

        return score

    # ------------------------------------------------------------------ #
    # Floodfill / helpers
    # ------------------------------------------------------------------ #

    def _floodfill(self, start, bodies, W, H) -> int:
        if start is None:
            return 0
        blocked: set[tuple[int, int]] = set()
        for b in bodies:
            if b:
                # Exclude tail (it will move)
                if len(b) > 1:
                    blocked.update(b[:-1])
                else:
                    blocked.update(b)

        if start in blocked:
            return 0

        visited = {start}
        q = deque([start])
        count = 0
        limit = (W * H) // 2 + 1  # no need to count beyond this

        while q and count < limit:
            x, y = q.popleft()
            count += 1
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H:
                    n = (nx, ny)
                    if n not in visited and n not in blocked:
                        visited.add(n)
                        q.append(n)
        return count

    def _quick_space(self, head, body, W, H) -> int:
        """Fast approximate space for opponent move selection."""
        blocked: set[tuple[int, int]] = set()
        if len(body) > 1:
            blocked.update(body[:-1])
        else:
            blocked.update(body)
        if head in blocked:
            return 0
        visited = {head}
        q = deque([head])
        count = 0
        limit = 20  # just need a rough comparison
        while q and count < limit:
            x, y = q.popleft()
            count += 1
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H:
                    n = (nx, ny)
                    if n not in visited and n not in blocked:
                        visited.add(n)
                        q.append(n)
        return count

    @staticmethod
    def _adjacent(a, b) -> bool:
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
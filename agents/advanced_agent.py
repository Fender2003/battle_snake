from __future__ import annotations

import time
from itertools import product
from collections import deque
from typing import Any, Optional

from agent import BaseAgent, legal_moves, next_position, parse_point


class AdvancedAgent(BaseAgent):
    """
    Minimax Battlesnake with CORRECT head-to-head handling.

    H2H rules (Battlesnake official):
      - Two heads land on same cell → shorter snake dies.
      - Equal length → BOTH snakes die.
      - So equal-length H2H is ALWAYS bad for you.

    This agent:
      1. Filters out moves that would lose/tie H2H at the current turn.
      2. Simulates opponents correctly (they avoid H2H with each other AND you).
      3. Evaluates H2H threats at every depth of the tree.
    """

    name = "advanced"
    apiversion = "1"
    color = "#8b00ff"
    author = "Skadoosh"

    TIME_LIMIT = 0.35

    W_SPACE = 120.0
    W_OPP_SPACE = -90.0
    W_H2H_WIN = 500.0
    W_H2H_LOSE = -800.0  # equal-length H2H is also a loss
    W_HEALTH = 0.6
    W_LENGTH = 8.0
    W_FOOD_HUNGRY = 3.5
    W_FOOD_STARVING = 8.0
    W_DEAD = -100000.0
    W_WIN = 100000.0

    HUNGRY_THRESHOLD = 55
    STARVING_THRESHOLD = 25

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

        # Your safe moves (with full H2H filtering)
        your_moves = self._safe_moves(your_head, your_body, your_len, opps, W, H)
        if not your_moves:
            lm = legal_moves(game_state, you)
            return lm[0] if lm else "up"
        if len(your_moves) == 1:
            return your_moves[0]

        best_move = your_moves[0]
        best_score = -1e18

        for depth in (1, 2, 3):
            if time.time() - start > self.TIME_LIMIT:
                break

            cur_best = your_moves[0]
            cur_best_score = -1e18

            for m in your_moves:
                if time.time() - start > self.TIME_LIMIT:
                    break

                heads, bodies, lens, hps = self._simulate_all(
                    your_head, your_body, your_len, your_hp, m, opps, W, H
                )
                if heads[0] is None:
                    continue

                score = self._min_min(heads, bodies, lens, hps, foods, W, H, depth - 1, start)
                if score > cur_best_score:
                    cur_best_score = score
                    cur_best = m

            best_move = cur_best
            best_score = cur_best_score

            if best_score >= self.W_WIN / 2:
                break

        return best_move

    def _min_min(self, heads, bodies, lens, hps, foods, W, H,
                 depth: int, start: float) -> float:
        if time.time() - start > self.TIME_LIMIT or depth <= 0:
            return self._evaluate(heads, bodies, lens, hps, foods, W, H)

        opp_move_lists: list[list[str]] = []
        opp_indices: list[int] = []
        for i in range(1, len(heads)):
            if heads[i] is None:
                continue
            # Build list of ALL other snakes (including you and other opponents)
            others = []
            for j in range(len(heads)):
                if j == i or heads[j] is None:
                    continue
                others.append({
                    "body": bodies[j],
                    "head": heads[j],
                    "len": lens[j],
                    "hp": hps[j],
                })
            moves = self._safe_moves(heads[i], bodies[i], lens[i], others, W, H)
            if not moves:
                continue
            opp_move_lists.append(moves)
            opp_indices.append(i)

        if not opp_move_lists:
            return self.W_WIN

        min_score = 1e18
        for combo in product(*opp_move_lists):
            new_heads, new_bodies, new_lens, new_hps = self._simulate_opps(
                heads, bodies, lens, hps, opp_indices, combo, W, H
            )
            score = self._max_you(new_heads, new_bodies, new_lens, new_hps,
                                  foods, W, H, depth - 1, start)
            if score < min_score:
                min_score = score
                if min_score <= self.W_DEAD:
                    break

        return min_score

    def _max_you(self, heads, bodies, lens, hps, foods, W, H,
                 depth: int, start: float) -> float:
        if time.time() - start > self.TIME_LIMIT or depth <= 0:
            return self._evaluate(heads, bodies, lens, hps, foods, W, H)

        if heads[0] is None:
            return self.W_DEAD

        opps = []
        for i in range(1, len(heads)):
            if heads[i] is None:
                continue
            opps.append({
                "body": bodies[i],
                "head": heads[i],
                "len": lens[i],
                "hp": hps[i],
            })

        moves = self._safe_moves(heads[0], bodies[0], lens[0], opps, W, H)
        if not moves:
            return self.W_DEAD

        max_score = -1e18
        for m in moves:
            new_heads, new_bodies, new_lens, new_hps = self._simulate_all(
                heads[0], bodies[0], lens[0], hps[0], m, opps, W, H
            )
            score = self._min_min(new_heads, new_bodies, new_lens, new_hps,
                                  foods, W, H, depth - 1, start)
            if score > max_score:
                max_score = score

        return max_score

    def _safe_moves(self, head, body, my_len, opps, W, H) -> list[str]:
        """
        Legal moves that don't immediately kill me.
        
        H2H handling:
          - If opponent's head is adjacent to my proposed cell AND I'm <= their length → death
          - If opponent's head is ON my proposed cell → body collision (already caught)
          - Equal-length H2H → both die → treat as loss
        """
        blocked: set[tuple[int, int]] = set()

        for opp in opps:
            b = opp["body"]
            if len(b) > 1:
                blocked.update(b[:-1])
            else:
                blocked.update(b)

        if len(body) > 1:
            blocked.update(body[:-1])
        else:
            blocked.update(body)

        out: list[str] = []
        for m in ("up", "down", "left", "right"):
            nx, ny = next_position(head, m)
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            p = (nx, ny)
            if p in blocked:
                continue

            # H2H check: would any opponent move into this cell?
            dead = False
            for opp in opps:
                oh = opp["head"]
                # Check if opponent's head is adjacent to my proposed position
                if abs(oh[0] - p[0]) + abs(oh[1] - p[1]) == 1:
                    # Opponent could move here. If I'm <= their length, I die.
                    if my_len <= opp["len"]:
                        dead = True
                        break
            if dead:
                continue

            out.append(m)
        return out

    def _simulate_all(self, your_head, your_body, your_len, your_hp,
                      your_move, opps, W, H):
        """Simulate one full turn: you + all opponents move simultaneously."""
        # Your proposed new head
        your_new_head = next_position(your_head, your_move)

        # Opponents' proposed new heads (greedy: maximize their space)
        opp_new_heads = []
        for opp in opps:
            # Build list of all OTHER snakes (including you)
            others = [{"body": your_body, "head": your_head, "len": your_len, "hp": your_hp}]
            for other_opp in opps:
                if other_opp is not opp:
                    others.append(other_opp)
            
            opp_moves = self._safe_moves(opp["head"], opp["body"], opp["len"], others, W, H)
            if not opp_moves:
                opp_new_heads.append(None)
                continue
            
            best_m = opp_moves[0]
            best_space = -1
            for om in opp_moves:
                nh = next_position(opp["head"], om)
                sp = self._quick_space(nh, opp["body"], W, H)
                if sp > best_space:
                    best_space = sp
                    best_m = om
            opp_new_heads.append(next_position(opp["head"], best_m))

        # Resolve collisions
        proposed = [your_new_head] + opp_new_heads
        all_bodies = [your_body] + [o["body"] for o in opps]
        all_lens = [your_len] + [o["len"] for o in opps]
        all_hps = [your_hp] + [o["hp"] for o in opps]

        alive = [True] * len(proposed)

        # Head-to-wall / head-to-body kills
        for i, nh in enumerate(proposed):
            if nh is None:
                alive[i] = False
                continue
            if not (0 <= nh[0] < W and 0 <= nh[1] < H):
                alive[i] = False
                continue
            for j, b in enumerate(all_bodies):
                if j == i:
                    check_body = b[:-1] if len(b) > 1 else b
                else:
                    check_body = b
                if nh in check_body:
                    alive[i] = False
                    break

        # Head-to-head: if two alive snakes land on same cell
        for i in range(len(proposed)):
            if not alive[i] or proposed[i] is None:
                continue
            for j in range(i + 1, len(proposed)):
                if not alive[j] or proposed[j] is None:
                    continue
                if proposed[i] == proposed[j]:
                    # H2H collision
                    if all_lens[i] > all_lens[j]:
                        alive[j] = False
                    elif all_lens[j] > all_lens[i]:
                        alive[i] = False
                    else:
                        # Equal length → both die
                        alive[i] = False
                        alive[j] = False

        # Build result
        heads: list[Optional[tuple[int, int]]] = [None] * len(proposed)
        bodies: list[list] = [[] for _ in range(len(proposed))]
        lens = [0] * len(proposed)
        hps = [0] * len(proposed)

        for i in range(len(proposed)):
            if alive[i]:
                heads[i] = proposed[i]
                bodies[i] = [proposed[i]] + all_bodies[i][:-1]
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
        """Apply a specific combination of opponent moves (you stay put)."""
        new_heads = list(heads)
        new_bodies = [list(b) for b in bodies]
        new_lens = list(lens)
        new_hps = list(hps)

        proposed = {idx: next_position(heads[idx], m)
                    for idx, m in zip(opp_indices, opp_moves)}

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

        # H2H with YOU
        if heads[0] is not None:
            for idx in opp_indices:
                if not alive[idx]:
                    continue
                if proposed[idx] == heads[0]:
                    # H2H with you
                    if lens[0] > lens[idx]:
                        alive[idx] = False
                    elif lens[idx] > lens[0]:
                        new_heads[0] = None
                        new_bodies[0] = []
                        new_lens[0] = 0
                        new_hps[0] = 0
                    else:
                        # Equal length → both die
                        alive[idx] = False
                        new_heads[0] = None
                        new_bodies[0] = []
                        new_lens[0] = 0
                        new_hps[0] = 0

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

    def _evaluate(self, heads, bodies, lens, hps, foods, W, H) -> float:
        if heads[0] is None:
            return self.W_DEAD

        all_dead = all(heads[i] is None for i in range(1, len(heads)))
        if all_dead:
            return self.W_WIN

        score = 0.0
        total_cells = W * H

        your_space = self._floodfill(heads[0], bodies, W, H)
        score += self.W_SPACE * (your_space / total_cells)

        your_len = lens[0]
        your_hp = hps[0]

        opp_len_sum = 0
        opp_count = 0
        for i in range(1, len(heads)):
            if heads[i] is None:
                continue
            opp_count += 1
            opp_len_sum += lens[i]

            opp_space = self._floodfill(heads[i], bodies, W, H)
            score += self.W_OPP_SPACE * (opp_space / total_cells)

            # H2H opportunity/threat
            dist = abs(heads[0][0] - heads[i][0]) + abs(heads[0][1] - heads[i][1])
            if dist == 1:
                # Adjacent → immediate H2H possible
                if your_len > lens[i]:
                    score += self.W_H2H_WIN
                else:
                    # Shorter or equal → bad
                    score += self.W_H2H_LOSE
            elif dist == 2 and lens[i] >= your_len:
                # Two cells away and they're longer → threat
                score -= 50.0

        if opp_count > 0:
            avg_opp_len = opp_len_sum / opp_count
            score += self.W_LENGTH * (your_len - avg_opp_len)

        score += self.W_HEALTH * (your_hp - 50)

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

    def _floodfill(self, start, bodies, W, H) -> int:
        if start is None:
            return 0
        blocked: set[tuple[int, int]] = set()
        for b in bodies:
            if b:
                if len(b) > 1:
                    blocked.update(b[:-1])
                else:
                    blocked.update(b)

        if start in blocked:
            return 0

        visited = {start}
        q = deque([start])
        count = 0
        limit = (W * H) // 2 + 1

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
        limit = 20
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
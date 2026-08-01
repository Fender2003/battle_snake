from __future__ import annotations

import time
from itertools import product
from collections import deque
from typing import Any, Optional

from agent import BaseAgent, legal_moves, next_position, parse_point


class SOTAAdvancedAgent(BaseAgent):
    """
    SOTA Heuristic Minimax for Battlesnake.
    Features: Relative Space Dominance, Dynamic Herding, Trap Avoidance.
    """

    name = "sota_advanced"
    apiversion = "1"
    color = "#ff0055"
    author = "Skadoosh"

    TIME_LIMIT = 0.42  # Hard cutoff for 500ms limit

    # Evaluation Weights
    W_SPACE_DOMINANCE = 15.0   # The most important SOTA weight
    W_HERDING = 8.0            # Shrinking opponent space
    W_FLEEING = 100.0          # Escaping longer snakes
    W_TRAP_PENALTY = -900000.0 # Instant death if trapped
    W_H2H_WIN = 1000.0
    W_H2H_LOSE = -1000.0
    W_MOMENTUM = 5.0
    W_CENTER = 1.5
    W_FOOD_URGENCY = 2.0
    W_DEAD = -1000000.0
    W_WIN = 1000000.0

    HUNGRY_THRESHOLD = 60
    STARVING_THRESHOLD = 30

    TT_EXACT = 0
    TT_LOWER = 1
    TT_UPPER = 2

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

    def _search(self, game_state: dict[str, Any], you: dict[str, Any], start: float) -> str:
        board = game_state["board"]
        W, H = board["width"], board["height"]
        foods = tuple(sorted(parse_point(f) for f in board.get("food", [])))

        you_id = you["id"]
        your_body = [parse_point(p) for p in you["body"]]
        your_head = your_body[0]
        your_len = len(your_body)
        your_hp = int(you.get("health", 100))
        current_dir = self._get_heading(you)

        opps = []
        for s in board.get("snakes", []):
            if s["id"] == you_id: continue
            body = [parse_point(p) for p in s.get("body", [])]
            if body:
                opps.append({
                    "body": body, "head": body[0],
                    "len": len(body), "hp": int(s.get("health", 100))
                })

        your_moves = self._safe_moves(your_head, your_body, your_len, opps, W, H)
        if not your_moves:
            lm = legal_moves(game_state, you)
            return lm[0] if lm else "up"
        if len(your_moves) == 1:
            return your_moves[0]

        # SOTA Move Ordering: Crucial for Alpha-Beta pruning efficiency
        your_moves = self._order_my_moves(your_moves, your_head, your_len, opps, W, H, current_dir)

        self.tt = {}
        best_move = your_moves[0]
        best_score = -1e18

        # Iterative deepening
        for depth in (1, 2, 3, 4):
            if time.time() - start > self.TIME_LIMIT: break

            alpha = -1e18
            beta = 1e18
            cur_best = your_moves[0]
            cur_best_score = -1e18

            for m in your_moves:
                if time.time() - start > self.TIME_LIMIT: break

                heads, bodies, lens, hps = self._simulate_all(
                    your_head, your_body, your_len, your_hp, m, opps, W, H
                )
                if heads[0] is None: continue

                score = self._min_min(heads, bodies, lens, hps, foods, W, H,
                                      depth - 1, start, alpha, beta, m, current_dir)
                
                if score > cur_best_score:
                    cur_best_score = score
                    cur_best = m
                alpha = max(alpha, cur_best_score)

            best_move = cur_best
            best_score = cur_best_score
            if best_score >= self.W_WIN / 2: break

        return best_move

    def _min_min(self, heads, bodies, lens, hps, foods, W, H, depth, start, alpha, beta, last_move, current_dir):
        if time.time() - start > self.TIME_LIMIT or depth <= 0:
            return self._evaluate(heads, bodies, lens, hps, foods, W, H, last_move, current_dir)

        tt_key = self._hash_state(heads, bodies, lens, hps, foods, depth, "MIN")
        if tt_key in self.tt:
            entry = self.tt[tt_key]
            if entry['depth'] >= depth:
                if entry['flag'] == self.TT_EXACT: return entry['score']
                elif entry['flag'] == self.TT_LOWER: alpha = max(alpha, entry['score'])
                elif entry['flag'] == self.TT_UPPER: beta = min(beta, entry['score'])
                if alpha >= beta: return entry['score']

        opp_move_lists = []
        opp_indices = []
        for i in range(1, len(heads)):
            if heads[i] is None: continue
            others = [{"body": bodies[j], "head": heads[j], "len": lens[j], "hp": hps[j]} 
                      for j in range(len(heads)) if j != i and heads[j] is not None]
            moves = self._safe_moves(heads[i], bodies[i], lens[i], others, W, H)
            if not moves: continue
            moves = self._order_opp_moves(moves, heads[i], lens[i], heads[0], lens[0], W, H)
            opp_move_lists.append(moves)
            opp_indices.append(i)

        if not opp_move_lists: return self.W_WIN

        orig_alpha = alpha
        min_score = 1e18
        
        for combo in product(*opp_move_lists):
            new_heads, new_bodies, new_lens, new_hps = self._simulate_opps(
                heads, bodies, lens, hps, opp_indices, combo, W, H
            )
            score = self._max_you(new_heads, new_bodies, new_lens, new_hps,
                                  foods, W, H, depth - 1, start, alpha, beta, last_move, current_dir)
            if score < min_score: min_score = score
            beta = min(beta, min_score)
            if alpha >= beta: break

        flag = self.TT_EXACT
        if min_score <= orig_alpha: flag = self.TT_UPPER
        elif min_score >= beta: flag = self.TT_LOWER
        self.tt[tt_key] = {'depth': depth, 'score': min_score, 'flag': flag}
        return min_score

    def _max_you(self, heads, bodies, lens, hps, foods, W, H, depth, start, alpha, beta, last_move, current_dir):
        if time.time() - start > self.TIME_LIMIT or depth <= 0:
            return self._evaluate(heads, bodies, lens, hps, foods, W, H, last_move, current_dir)

        if heads[0] is None: return self.W_DEAD

        tt_key = self._hash_state(heads, bodies, lens, hps, foods, depth, "MAX")
        if tt_key in self.tt:
            entry = self.tt[tt_key]
            if entry['depth'] >= depth:
                if entry['flag'] == self.TT_EXACT: return entry['score']
                elif entry['flag'] == self.TT_LOWER: alpha = max(alpha, entry['score'])
                elif entry['flag'] == self.TT_UPPER: beta = min(beta, entry['score'])
                if alpha >= beta: return entry['score']

        opps = [{"body": bodies[i], "head": heads[i], "len": lens[i], "hp": hps[i]} 
                for i in range(1, len(heads)) if heads[i] is not None]

        moves = self._safe_moves(heads[0], bodies[0], lens[0], opps, W, H)
        if not moves: return self.W_DEAD

        moves = self._order_my_moves(moves, heads[0], lens[0], opps, W, H, current_dir)

        orig_alpha = alpha
        max_score = -1e18
        
        for m in moves:
            new_heads, new_bodies, new_lens, new_hps = self._simulate_all(
                heads[0], bodies[0], lens[0], hps[0], m, opps, W, H
            )
            score = self._min_min(new_heads, new_bodies, new_lens, new_hps,
                                  foods, W, H, depth - 1, start, alpha, beta, m, current_dir)
            if score > max_score: max_score = score
            alpha = max(alpha, max_score)
            if alpha >= beta: break

        flag = self.TT_EXACT
        if max_score <= orig_alpha: flag = self.TT_UPPER
        elif max_score >= beta: flag = self.TT_LOWER
        self.tt[tt_key] = {'depth': depth, 'score': max_score, 'flag': flag}
        return max_score

    # ==========================================
    # SOTA EVALUATION FUNCTION
    # ==========================================
    def _evaluate(self, heads, bodies, lens, hps, foods, W, H, last_move, current_dir):
        if heads[0] is None: return self.W_DEAD
        if all(heads[i] is None for i in range(1, len(heads))): return self.W_WIN

        my_len = lens[0]
        my_hp = hps[0]
        
        # 1. Calculate our space
        my_space = self._floodfill(heads[0], bodies, W, H)
        
        # SOTA TRAP PENALTY: If we have less space than our length, we are trapped.
        if my_space < my_len:
            return self.W_TRAP_PENALTY

        score = 0.0
        max_opp_space = 0
        opp_spaces = []
        
        # 2. Calculate opponent spaces and distances
        for i in range(1, len(heads)):
            if heads[i] is None: continue
            opp_space = self._floodfill(heads[i], bodies, W, H)
            opp_spaces.append(opp_space)
            if opp_space > max_opp_space:
                max_opp_space = opp_space

        # 3. SOTA SPACE DOMINANCE (The most important heuristic)
        # We don't just want space; we want MORE space than the biggest threat.
        space_dominance = my_space - max_opp_space
        score += space_dominance * self.W_SPACE_DOMINANCE

        # 4. DYNAMIC HERDING & FLEEING (Per-opponent logic)
        for i in range(1, len(heads)):
            if heads[i] is None: continue
            opp_len = lens[i]
            opp_space = opp_spaces[i-1]
            dist = abs(heads[0][0] - heads[i][0]) + abs(heads[0][1] - heads[i][1])

            if my_len > opp_len:
                # AGGRESSIVE: Herd them. Penalize them for having space.
                score += (50 - opp_space) * self.W_HERDING
                if dist <= 4:
                    score += (5 - dist) * 20.0  # Bonus for closing in to cut them off
            elif my_len < opp_len:
                # DEFENSIVE: Flee. The closer they are, the worse.
                if dist <= 4:
                    score -= (5 - dist) * self.W_FLEEING
            else:
                # EQUAL LENGTH: Avoid H2H at all costs.
                if dist <= 2:
                    score -= 200.0

        # 5. SAFE FOOD VALUATION
        if foods:
            best_food_score = -9999
            for f in foods:
                dist_to_food = abs(heads[0][0] - f[0]) + abs(heads[0][1] - f[1])
                food_score = -dist_to_food * self.W_FOOD_URGENCY
                
                # Urgency multiplier based on health
                if my_hp <= self.STARVING_THRESHOLD: food_score *= 4.0
                elif my_hp <= self.HUNGRY_THRESHOLD: food_score *= 2.5
                elif my_len <= 3: food_score *= 2.0
                
                if food_score > best_food_score:
                    best_food_score = food_score
            score += best_food_score

        # 6. Smoothness (Momentum & Center)
        if current_dir and last_move == current_dir:
            score += self.W_MOMENTUM

        center_x, center_y = (W - 1) / 2.0, (H - 1) / 2.0
        dist_to_center = abs(heads[0][0] - center_x) + abs(heads[0][1] - center_y)
        score -= dist_to_center * self.W_CENTER

        return score

    # ==========================================
    # HELPER FUNCTIONS
    # ==========================================
    def _order_my_moves(self, moves, head, my_len, opps, W, H, current_dir):
        scored = []
        for m in moves:
            nh = next_position(head, m)
            score = 0.0
            
            # Immediate H2H kill/death
            for opp in opps:
                if abs(opp["head"][0] - nh[0]) + abs(opp["head"][1] - nh[1]) == 1:
                    if my_len > opp["len"]: score += 1000.0
                    elif my_len == opp["len"]: score -= 500.0
                    else: score -= 1000.0
                    
            # Fast space proxy (count open neighbors)
            open_neighbors = 0
            for dx, dy in ((0,1),(0,-1),(1,0),(-1,0)):
                nx, ny = nh[0]+dx, nh[1]+dy
                if 0<=nx<W and 0<=ny<H:
                    blocked = any((nx,ny) in opp["body"] for opp in opps)
                    if not blocked: open_neighbors += 1
            score += open_neighbors * 15.0
            
            cx, cy = (W-1)/2, (H-1)/2
            score -= (abs(nh[0]-cx) + abs(nh[1]-cy)) * 0.5
            if current_dir and m == current_dir: score += 5.0
            
            scored.append((score, m))
        scored.sort(reverse=True)
        return [m for _, m in scored]

    def _order_opp_moves(self, moves, opp_head, opp_len, my_head, my_len, W, H):
        scored = []
        for m in moves:
            nh = next_position(opp_head, m)
            score = 0.0
            dist = abs(my_head[0] - nh[0]) + abs(my_head[1] - nh[1])
            
            if opp_len >= my_len:
                score -= dist * 10.0  # They want to get closer to kill us
            else:
                score += dist * 10.0  # They want to run away
                
            scored.append((score, m))
        scored.sort(reverse=True)
        return [m for _, m in scored]

    def _hash_state(self, heads, bodies, lens, hps, foods, depth, turn):
        # FIXED: Included hps and foods to prevent TT collisions
        return (tuple(heads), tuple(tuple(b) for b in bodies), tuple(lens), tuple(hps), foods, depth, turn)

    def _safe_moves(self, head, body, my_len, opps, W, H):
        blocked = set()
        for opp in opps:
            b = opp["body"]
            blocked.update(b[:-1] if len(b) > 1 else b)
        blocked.update(body[:-1] if len(body) > 2 else body)

        out = []
        for m in ("up", "down", "left", "right"):
            nx, ny = next_position(head, m)
            if not (0 <= nx < W and 0 <= ny < H): continue
            p = (nx, ny)
            if p in blocked: continue

            dead = False
            for opp in opps:
                oh = opp["head"]
                if abs(oh[0] - p[0]) + abs(oh[1] - p[1]) == 1:
                    if my_len <= opp["len"]:
                        dead = True; break
            if dead: continue
            out.append(m)
        return out

    def _simulate_all(self, your_head, your_body, your_len, your_hp, your_move, opps, W, H):
        your_new_head = next_position(your_head, your_move)
        opp_new_heads = []
        for opp in opps:
            others = [{"body": your_body, "head": your_head, "len": your_len, "hp": your_hp}]
            others += [o for o in opps if o is not opp]
            opp_moves = self._safe_moves(opp["head"], opp["body"], opp["len"], others, W, H)
            if not opp_moves:
                opp_new_heads.append(None); continue
            best_m = self._pick_opp_move(opp, opp_moves, your_head, your_len, W, H)
            opp_new_heads.append(next_position(opp["head"], best_m))

        proposed = [your_new_head] + opp_new_heads
        all_bodies = [your_body] + [o["body"] for o in opps]
        all_lens = [your_len] + [o["len"] for o in opps]
        all_hps = [your_hp] + [o["hp"] for o in opps]
        alive = [True] * len(proposed)

        for i, nh in enumerate(proposed):
            if nh is None or not (0 <= nh[0] < W and 0 <= nh[1] < H):
                alive[i] = False; continue
            for j, b in enumerate(all_bodies):
                check_body = b[:-1] if j == i and len(b) > 1 else b
                if nh in check_body: alive[i] = False; break

        for i in range(len(proposed)):
            if not alive[i] or proposed[i] is None: continue
            for j in range(i + 1, len(proposed)):
                if not alive[j] or proposed[j] is None: continue
                if proposed[i] == proposed[j]:
                    if all_lens[i] > all_lens[j]: alive[j] = False
                    elif all_lens[j] > all_lens[i]: alive[i] = False
                    else: alive[i] = False; alive[j] = False

        heads = [None] * len(proposed)
        bodies = [[] for _ in range(len(proposed))]
        lens = [0] * len(proposed)
        hps = [0] * len(proposed)

        for i in range(len(proposed)):
            if alive[i]:
                heads[i] = proposed[i]
                bodies[i] = [proposed[i]] + all_bodies[i][:-1]
                lens[i] = all_lens[i]
                hps[i] = max(0, all_hps[i] - 1)
        return heads, bodies, lens, hps

    def _pick_opp_move(self, opp, opp_moves, my_head, my_len, W, H):
        opp_head = opp["head"]
        opp_len = opp["len"]
        best_m, best_score = opp_moves[0], -9999
        
        for om in opp_moves:
            nh = next_position(opp_head, om)
            score = 0.0
            dist = abs(nh[0] - my_head[0]) + abs(nh[1] - my_head[1])
            
            if opp_len > my_len:
                score -= dist * 10.0  # Hunt us
                score += self._quick_space(nh, opp["body"], W, H) * 2.0
            else:
                score += dist * 10.0  # Run from us
                score += self._quick_space(nh, opp["body"], W, H) * 5.0
                
            if score > best_score: best_score = score; best_m = om
        return best_m

    def _simulate_opps(self, heads, bodies, lens, hps, opp_indices, opp_moves, W, H):
        new_heads, new_bodies, new_lens, new_hps = list(heads), [list(b) for b in bodies], list(lens), list(hps)
        proposed = {idx: next_position(heads[idx], m) for idx, m in zip(opp_indices, opp_moves)}
        alive = {idx: True for idx in opp_indices}

        for idx, nh in proposed.items():
            if not (0 <= nh[0] < W and 0 <= nh[1] < H): alive[idx] = False; continue
            if heads[0] is not None:
                yb = bodies[0][:-1] if len(bodies[0]) > 1 else bodies[0]
                if nh in yb: alive[idx] = False; continue
            for j in opp_indices:
                if j == idx or not alive.get(j, False): continue
                if nh in bodies[j]: alive[idx] = False; break

        if heads[0] is not None:
            for idx in opp_indices:
                if not alive[idx]: continue
                if proposed[idx] == heads[0]:
                    if lens[0] > lens[idx]: alive[idx] = False
                    elif lens[idx] > lens[0]:
                        new_heads[0], new_bodies[0], new_lens[0], new_hps[0] = None, [], 0, 0
                    else:
                        alive[idx], new_heads[0], new_bodies[0], new_lens[0], new_hps[0] = False, None, [], 0, 0

        for i_idx in opp_indices:
            if not alive[i_idx]: continue
            for j_idx in opp_indices:
                if i_idx >= j_idx or not alive[j_idx]: continue
                if proposed[i_idx] == proposed[j_idx]:
                    if lens[i_idx] > lens[j_idx]: alive[j_idx] = False
                    elif lens[j_idx] > lens[i_idx]: alive[i_idx] = False
                    else: alive[i_idx] = False; alive[j_idx] = False

        for idx in opp_indices:
            if alive[idx]:
                new_heads[idx] = proposed[idx]
                new_bodies[idx] = [proposed[idx]] + bodies[idx][:-1]
                new_hps[idx] = max(0, hps[idx] - 1)
            else:
                new_heads[idx], new_bodies[idx], new_lens[idx], new_hps[idx] = None, [], 0, 0
        return new_heads, new_bodies, new_lens, new_hps

    def _floodfill(self, start, bodies, W, H):
        if start is None: return 0
        blocked = set()
        for b in bodies:
            if b: blocked.update(b[:-1] if len(b) > 1 else b)
        if start in blocked: return 0

        visited = {start}
        q = deque([start])
        count = 0
        while q and count < 60: # 60 is ~50% of 11x11, enough to prove dominance
            x, y = q.popleft()
            count += 1
            for dx, dy in ((0,1),(0,-1),(1,0),(-1,0)):
                nx, ny = x+dx, y+dy
                if 0<=nx<W and 0<=ny<H:
                    n = (nx, ny)
                    if n not in visited and n not in blocked:
                        visited.add(n); q.append(n)
        return count

    def _quick_space(self, head, body, W, H):
        blocked = set(body[:-1] if len(body) > 1 else body)
        if head in blocked: return 0
        visited = {head}
        q = deque([head])
        count = 0
        while q and count < 20:
            x, y = q.popleft()
            count += 1
            for dx, dy in ((0,1),(0,-1),(1,0),(-1,0)):
                nx, ny = x+dx, y+dy
                if 0<=nx<W and 0<=ny<H:
                    n = (nx, ny)
                    if n not in visited and n not in blocked:
                        visited.add(n); q.append(n)
        return count

    def _get_heading(self, you):
        body = you.get("body", [])
        if len(body) < 2: return None
        head = parse_point(body[0])
        neck = parse_point(body[1])
        dx, dy = head[0] - neck[0], head[1] - neck[1]
        if dx == 0 and dy == 1: return "up"
        if dx == 0 and dy == -1: return "down"
        if dx == 1 and dy == 0: return "right"
        if dx == -1 and dy == 0: return "left"
        return None
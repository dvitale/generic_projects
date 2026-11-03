"""Stockfish boundary: keep every comparison in the decision maker's perspective."""
import json
import math
import os
import threading
from pathlib import Path

import chess
import chess.engine

ROOT = Path(__file__).resolve().parents[1]


def stockfish_path():
    configured = os.environ.get("STOCKFISH_PATH")
    if configured:
        return configured
    candidates = list((ROOT / "vendor").glob("**/stockfish-ubuntu*"))
    candidates += list((ROOT / "vendor").glob("**/stockfish-linux*"))
    candidates += list((ROOT / "vendor").glob("**/stockfish"))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK) and not candidate.name.endswith(".tar.gz"):
            return str(candidate)
    if Path("/usr/games/stockfish").exists():
        return "/usr/games/stockfish"
    raise RuntimeError("Stockfish non trovato. Imposta STOCKFISH_PATH.")


# A line that ends where the engine's next move is a capture or a check is continued by SETTLE_PLIES,
# at most SETTLE_STEPS times, each step judged with SETTLE_NODES (idea from the Queen paper, arXiv 2610.03695).
SETTLE_NODES, SETTLE_PLIES, SETTLE_STEPS = 10000, 2, 6


class Evaluator:
    def __init__(self):
        self.lock = threading.RLock()
        self.engine = None
        self.name = "Non avviato"

    def start(self):
        with self.lock:
            if self.engine is None:
                self.engine = chess.engine.SimpleEngine.popen_uci(stockfish_path(), timeout=30)
                self.engine.configure({"Threads": 2, "Hash": 64})
                self.name = self.engine.id.get("name", "Stockfish")

    def close(self):
        with self.lock:
            if self.engine:
                self.engine.quit()
                self.engine = None

    def _analyse(self, board, nodes, **kwargs):
        # Callers hold the reentrant lock throughout analysis and comparison.
        self.start()
        try:
            return self.engine.analyse(board, chess.engine.Limit(nodes=nodes), **kwargs)
        except chess.engine.EngineTerminatedError:
            self.engine = None
            self.start()
            return self.engine.analyse(board, chess.engine.Limit(nodes=nodes), **kwargs)

    @staticmethod
    def _format(board, info):
        score = info["score"].pov(board.turn)
        cursor = board.copy()
        san, uci = [], []
        for step in info.get("pv", [])[:8]:
            if step not in cursor.legal_moves:
                break
            san.append(cursor.san(step))
            uci.append(step.uci())
            cursor.push(step)
        return {"cp": score.score(mate_score=100000), "mate": score.mate(),
                "pv": uci, "san": san, "depth": info.get("depth", 0),
                "nodes": info.get("nodes", 0), "perspective": "w" if board.turn else "b"}

    def evaluate(self, board, move=None, nodes=12000):
        with self.lock:
            kwargs = {"root_moves": [move]} if move else {}
            return self._format(board, self._analyse(board, nodes, **kwargs))

    def candidates(self, board, nodes=12000, count=3):
        with self.lock:
            count = min(count, board.legal_moves.count())
            if count < 1:
                return []
            # MultiPV ranks distinct root moves, not subsequent moves in one variation.
            infos = self._analyse(board, nodes * count, multipv=count)
            # A node-limited search can stop partway through a MultiPV iteration;
            # its numbered lines may then contain scores from different depths.
            # Rank the returned evaluations consistently for comparison and display.
            return sorted((self._format(board, info) for info in infos), key=lambda value: value['cp'], reverse=True)

    def rank(self, board, moves, nodes=12000):
        """Each given root move with its own line, in one MultiPV search restricted to those moves."""
        with self.lock:
            infos = self._analyse(board, nodes * len(moves), multipv=len(moves), root_moves=moves)
            return [self._format(board, info) for info in infos if info.get("pv")]

    def settle(self, board, evaluation, nodes=SETTLE_NODES):
        """The line continued while the engine's next move at its end is a capture or a check: never cut mid-exchange."""
        with self.lock:
            cursor = board.copy(stack=False)
            for uci in evaluation["pv"]:
                cursor.push_uci(uci)
            pv, san = list(evaluation["pv"]), list(evaluation["san"])
            for _ in range(SETTLE_STEPS):
                if not pv or cursor.is_game_over():
                    break
                follow = self._analyse(cursor, nodes).get("pv", [])[:SETTLE_PLIES]
                if not follow or not (cursor.is_capture(follow[0]) or cursor.gives_check(follow[0])):
                    break
                for move in follow:
                    if move not in cursor.legal_moves:
                        break
                    san.append(cursor.san(move))
                    pv.append(move.uci())
                    cursor.push(move)
            return {**evaluation, "pv": pv, "san": san} if len(pv) > len(evaluation["pv"]) else evaluation

    def compare_candidates(self, board, played, nodes=24000):
        with self.lock:
            choices = self.candidates(board, nodes=nodes)
            actual = next((c for c in choices if c["pv"] and c["pv"][0] == played.uci()), None)
            if actual is None:
                actual = self.evaluate(board, played, nodes)
            if actual["cp"] > choices[0]["cp"] + 30:
                choices = self.candidates(board, nodes=nodes * 2)
                actual = next((c for c in choices if c["pv"] and c["pv"][0] == played.uci()), actual)
            best = choices[0]
            settled = {id(best): self.settle(board, best)}
            settled.setdefault(id(actual), self.settle(board, actual))
            choices = [settled.get(id(c), c) for c in choices]
            return settled[id(best)], settled[id(actual)], review_loss(best, actual), choices

    def compare(self, board, played, nodes=24000):
        # One lock prevents interleaved jobs from changing the engine's state mid-comparison.
        with self.lock:
            best = self.evaluate(board, nodes=nodes)
            actual = best if best["pv"] and best["pv"][0] == played.uci() else self.evaluate(board, played, nodes)
            if actual["cp"] > best["cp"] + 30:
                best = self.evaluate(board, nodes=nodes * 2)
            settled = self.settle(board, best)
            actual = settled if actual is best else self.settle(board, actual)
            return settled, actual, review_loss(settled, actual)


def expected(e):
    """Expected score of the side to move, Lichess's logistic curve on centipawns."""
    if e['mate'] is not None:
        return 1.0 if e['mate'] > 0 else 0.0
    return 1 / (1 + math.exp(-0.00368208 * e['cp']))


# Outcome cap ("franchigia"): beyond +OUTCOME_CAP_CP the game is won and below -OUTCOME_CAP_CP it is lost; a bigger
# margin changes nothing (+12 or +18, 3 or 1200 metres of water). Every mate counts as the cap, so a loss only measures
# how far a move moves the game towards a different outcome, and engine noise in decided positions is ignored.
OUTCOME_CAP_CP = 600
# Mates in 1-2 are judged apart: missing one is a "Matto mancato" even when the position stays won.
SHORT_MATE = 2
INACCURACY_CP, ERROR_CP = 80, 180


def capped(e):
    if e['mate'] is not None:
        return OUTCOME_CAP_CP if e['mate'] > 0 else -OUTCOME_CAP_CP
    return max(-OUTCOME_CAP_CP, min(OUTCOME_CAP_CP, e['cp']))


def review_loss(best, actual):
    """Loss of a move against the best one, on the capped outcome scale: the one rule for reviews, puzzles and exams."""
    return max(0, capped(best) - capped(actual))


def short_mate(e):
    return e['mate'] is not None and 0 < e['mate'] <= SHORT_MATE


def missed_mate(best, actual):
    """A mate in 1-2 was there and the move played does not mate as quickly."""
    return short_mate(best) and not short_mate(actual)


def review_label(d):
    if d.get('forced'):
        return 'Mossa obbligata'
    if d.get('missedMate'):
        return 'Matto mancato'
    return 'Errore' if d['loss'] >= ERROR_CP else 'Imprecisione' if d['loss'] >= INACCURACY_CP else 'Buona scelta'


def flagged(d):
    """A decision worth reviewing: an inaccuracy, an error or a missed mate."""
    return d['loss'] >= INACCURACY_CP or bool(d.get('missedMate'))


def severity(d):
    """Ordering key for the costliest decisions; a missed mate weighs at least as an error."""
    return max(d['loss'], ERROR_CP) if d.get('missedMate') else d['loss']


def rescore(d):
    d['loss'] = review_loss(d['best'], d['actual'])
    d['missedMate'] = missed_mate(d['best'], d['actual'])
    d['label'] = review_label(d)
    return d


def critical(decisions):
    return sorted([d for d in decisions if flagged(d)], key=lambda d: -severity(d))[:3]


def load_analysis(text):
    """Stored game analysis rescored by the current rule (loss, missed mate, label), so older analyses follow it."""
    analysis = json.loads(text)
    for key in ('moves', 'decisions', 'critical'):
        for d in analysis.get(key, []):
            rescore(d)
    if 'critical' in analysis:
        analysis['critical'] = critical(analysis.get('decisions', []))
    return analysis


evaluator = Evaluator()

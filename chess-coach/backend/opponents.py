"""Human-like opponents for Play: Maia in the browser, or the experimental policy behind a local service.

Common adapter: position, requested Elo and game context in; every legal move with its probability, engine
and model version out. The experimental service is enabled by SPARRINGMATE_EXPERIMENTAL_ENGINE (environment
or .env, read on every request): without it the selector is hidden. A failing service stops the game with a
message; there is never a silent fallback to Maia.
"""
import json
import math
import os
import random
import urllib.error
import urllib.request

from .auth import read_env

MAIA = 'maia'
EXPERIMENTAL = 'experimental'
ENGINES = {MAIA: 'Maia', EXPERIMENTAL: 'Sperimentale'}
# Default: draw from the model's whole distribution, no truncation. The experimental engine always uses it.
SELECTION = 'sample-full-distribution'
# Maia move selection, fixed when the game starts and applied by the browser (web/src/engine/maia.ts).
MAIA_SELECTIONS = {SELECTION: 'Completa', 'temperature-0.7-top-p-0.95': 'Bilanciata',
                   'temperature-0.4-top-p-0.8': 'Solida', 'top-move': 'Prima scelta'}
HEALTH_TIMEOUT = 2
PREDICT_TIMEOUT = 10
# The service rounds through float32: the distribution must still add up to one.
SUM_TOLERANCE = 1e-3


class PolicyError(Exception):
    """The experimental service cannot provide a usable move: shown to the player, who may retry."""


def service_url(env_path):
    url = os.environ.get('SPARRINGMATE_EXPERIMENTAL_ENGINE') or read_env(env_path).get('SPARRINGMATE_EXPERIMENTAL_ENGINE', '')
    return url.rstrip('/')


def call(url, path, body=None, timeout=PREDICT_TIMEOUT):
    request = urllib.request.Request(url + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read()).get('error')
        except (ValueError, AttributeError):
            detail = None
        if error.code >= 500:
            raise PolicyError(f'Errore del motore sperimentale ({detail or error.code}). Riprova.') from error
        raise PolicyError(f'Il motore sperimentale ha rifiutato la richiesta: {detail or error.code}') from error
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        raise PolicyError('Il motore sperimentale non risponde. Controlla che il servizio sia avviato e riprova.') from error


def status(env_path):
    url = service_url(env_path)
    if not url:
        return {'enabled': False}
    try:
        health = call(url, '/health', timeout=HEALTH_TIMEOUT)
        bounds = health['ratingBounds']
        return {'enabled': True, 'available': True, 'engine': str(health['engine']), 'version': str(health['version']),
                'ratingBounds': [int(math.ceil(bounds[0])), int(math.floor(bounds[1]))], 'calibrated': bool(health.get('calibrated'))}
    except (PolicyError, KeyError, TypeError, IndexError, ValueError) as error:
        return {'enabled': True, 'available': False,
                'error': str(error) if isinstance(error, PolicyError) else 'Risposta di stato non valida'}


def predict(env_path, board, elo, version, context):
    """Every legal move with its probability, checked against the position and the version fixed at game start."""
    url = service_url(env_path)
    if not url:
        raise PolicyError('Il motore sperimentale è disattivato nella configurazione.')
    result = call(url, '/predict', {'fen': board.fen(), 'elo': elo, 'context': context})
    try:
        moves = [(str(m['uci']), float(m['probability'])) for m in result['moves']]
        served = str(result['version'])
    except (KeyError, TypeError, ValueError) as error:
        raise PolicyError('Risposta del motore sperimentale non valida.') from error
    if served != version:
        raise PolicyError(f'Il servizio usa il modello {served}, ma la partita è iniziata con {version}. '
                          'Riavvia il servizio con lo stesso modello o inizia una nuova partita.')
    legal = {m.uci() for m in board.legal_moves}
    if len(moves) != len(legal) or {uci for uci, _ in moves} != legal:
        raise PolicyError('Il motore sperimentale ha restituito mosse diverse da quelle legali.')
    if any(not math.isfinite(p) or p < 0 for _, p in moves) or abs(sum(p for _, p in moves) - 1) > SUM_TOLERANCE:
        raise PolicyError('Il motore sperimentale ha restituito probabilità non valide.')
    return moves


def sample(moves, seed):
    """Draw from the whole distribution; sorting by UCI makes the choice depend only on the seed."""
    ordered = sorted(moves)
    total = sum(p for _, p in ordered)
    draw = random.Random(seed).random() * total
    for uci, probability in ordered:
        draw -= probability
        if draw < 0:
            return uci, probability
    # Rounding left a sliver: the last move with positive probability.
    return next((m for m in reversed(ordered) if m[1] > 0), ordered[-1])


def label(row):
    return ENGINES.get(row['engine'] or MAIA, row['engine'])

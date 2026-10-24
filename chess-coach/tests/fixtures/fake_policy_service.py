"""Stand-in for experiments/human-policy/serve.py in tests: same HTTP contract, no neural network.

Probabilities favour the first legal moves in UCI order. POST /control {"mode": ...} switches the next answers
to a failure: 'down' (HTTP 500), 'illegal', 'partial', 'badsum', 'version' or back to 'ok'.
"""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import chess

VERSION = 'fake-step1-000000000000'


def distribution(fen):
    moves = sorted(m.uci() for m in chess.Board(fen).legal_moves)
    weights = [len(moves) - i for i in range(len(moves))]
    return [{'uci': uci, 'probability': w / sum(weights)} for uci, w in zip(moves, weights)]


def make_server(port=0):
    state = {'mode': 'ok', 'requests': []}

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != '/health' or state['mode'] == 'down':
                return self.reply(500, {'error': 'non disponibile'})
            self.reply(200, {'engine': 'sparringmate-human-policy', 'version': VERSION, 'ratingBounds': [600, 2596], 'calibrated': False})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
            if self.path == '/control':
                state['mode'] = body['mode']
                return self.reply(200, state | {'requests': len(state['requests'])})
            state['requests'].append(body)
            mode = state['mode']
            if mode == 'down':
                return self.reply(500, {'error': 'servizio guasto'})
            moves = distribution(body['fen'])
            if mode == 'illegal':
                moves[0]['uci'] = 'a1a1'
            elif mode == 'partial':
                moves = moves[:1]
            elif mode == 'badsum':
                moves[0]['probability'] += 0.5
            self.reply(200, {'engine': 'sparringmate-human-policy', 'version': 'other-version' if mode == 'version' else VERSION,
                             'elo': body['elo'], 'moves': moves})

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler), state


def start(port=0):
    server, state = make_server(port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, state


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8012)
    make_server(parser.parse_args().port)[0].serve_forever()

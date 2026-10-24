import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import chess
import pytest
import torch

from policy import Config, Policy
from serve import Model, handler

torch.set_num_threads(2)


@pytest.fixture
def service(tmp_path):
    torch.manual_seed(0)
    path = tmp_path / "run" / "best.pt"
    path.parent.mkdir()
    torch.save({"config": vars(Config()), "model": Policy().state_dict(), "rating_bounds": [600, 2400],
                "step": 7, "dataset": {"speed": "rapid"}}, path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(Model(path)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def call(url, body=None):
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_health_names_engine_version_and_bounds(service):
    status, health = call(service + "/health")
    assert status == 200 and health["engine"] == "sparringmate-human-policy"
    assert health["version"].startswith("run-step7-") and health["ratingBounds"] == [600, 2400]
    assert health["calibrated"] is False
    status, root = call(service + "/")
    assert status == 200 and "SPARRINGMATE_EXPERIMENTAL_ENGINE" in root["info"] and root["version"] == health["version"]


@pytest.mark.parametrize("fen", [chess.STARTING_FEN, "4k3/P7/8/8/8/8/7p/4K3 w - - 0 1", "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1"])
def test_predict_returns_the_whole_legal_distribution(service, fen):
    status, result = call(service + "/predict", {"fen": fen, "elo": 1500})
    assert status == 200
    board = chess.Board(fen)
    assert sorted(m["uci"] for m in result["moves"]) == sorted(m.uci() for m in board.legal_moves)
    assert sum(m["probability"] for m in result["moves"]) == pytest.approx(1, abs=1e-5)


def test_predict_rejects_bad_input_and_handles_finished_games(service):
    assert call(service + "/predict", {"fen": "nonsense", "elo": 1500})[0] == 422
    assert call(service + "/predict", {"fen": chess.STARTING_FEN, "elo": 2600})[0] == 422
    mate = "7k/6Q1/5K2/8/8/8/8/8 b - - 0 1"
    assert call(service + "/predict", {"fen": mate, "elo": 1500})[1]["moves"] == []

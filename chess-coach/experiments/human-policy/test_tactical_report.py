import pytest
from tactical_report import loss_metrics, report


def test_cp_loss_remains_visible_when_wdl_saturates():
    labels = [{'uci':'g8f6','loss_cp':750,'severe':False},
              {'uci':'f4g4','loss_cp':0,'severe':False}]
    result = loss_metrics(labels,{'g8f6':.9,'f4g4':.1})
    assert result['cp500_mass'] == pytest.approx(.9)
    assert result['cp200_mass'] == pytest.approx(.9)
    assert result['wdl_severe_mass'] == 0
    with pytest.raises(ValueError,match='move sets'):
        loss_metrics(labels,{'g8f6':1.})


def test_report_refuses_incomplete_arms(tmp_path):
    for name in ('manifest','comparison'):
        (tmp_path/f'{name}.json').write_text('{}')
    (tmp_path/'stockfish-labels.json').write_text('[]')
    with pytest.raises(ValueError,match='Wait'):
        report(tmp_path)

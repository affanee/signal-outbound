import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from signal_outbound.guard import check, extract_names, extract_numbers

SIG = "Northwind Signals raised a $42M Series B led by Fernbrook Ventures to expand its go-to-market team."
EV = SIG + " | Priya | Raman | VP Revenue Operations | Northwind Signals"


def test_faithful_line_passes():
    assert check("Congrats on the $42M Series B, Priya — expanding go-to-market is a big moment.", EV, SIG).ok

def test_inflated_amount_is_caught():
    v = check("Congrats on the $50M Series B, Priya.", EV, SIG)
    assert not v.ok and "$50M" in v.unsupported_numbers

def test_wrong_round_is_caught():
    v = check("Congrats on the $42M Series C, Priya — go-to-market time.", EV, SIG)
    assert not v.ok and "Series C" in v.unsupported_names

def test_invented_investor_is_caught():
    v = check("Priya — saw Sequoia led the go-to-market round.", EV, SIG)
    assert not v.ok and "Sequoia" in v.unsupported_names

def test_real_investor_passes():
    assert check("Priya — saw Fernbrook Ventures backed the go-to-market expansion.", EV, SIG).ok

def test_invented_headcount_is_caught():
    v = check("Priya, at 400+ people the go-to-market team must be busy.", EV, SIG)
    assert not v.ok and any("400" in n for n in v.unsupported_numbers)

def test_generic_line_is_rejected():
    v = check("Hi Priya, hope you're well — quick question about your stack.", EV, SIG)
    assert not v.ok and v.generic

def test_sentence_starting_words_are_not_names():
    assert "Congrats" not in extract_names("Congrats on the round.")

def test_number_extraction():
    assert any("42" in n for n in extract_numbers("a $42M round"))

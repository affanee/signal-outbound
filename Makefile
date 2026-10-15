.PHONY: test demo naive again reset clean

## 19 tests. No network, no keys.
test:
	PYTHONPATH=src python -m pytest tests -q

## The real writer. Starts fresh, writes out/sequencer_import.csv
demo:
	PYTHONPATH=src python -m signal_outbound run --today 2026-09-21 --reset

## A SIMULATED careless AI writer, and the fact guard catching it
naive:
	PYTHONPATH=src python -m signal_outbound run --today 2026-09-21 --writer naive

## Run again the same day: every account is on cooldown, nothing goes out
again:
	PYTHONPATH=src python -m signal_outbound run --today 2026-09-21

reset:
	rm -rf data/state.db out

clean: reset
	rm -rf .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +

PYTHON ?= python3

.PHONY: test verify

test:
	$(PYTHON) -m unittest -v tests/test_mapping.py

verify: test


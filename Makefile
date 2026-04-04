PYTHON ?= python3

.PHONY: test verify lock mirror-wheels

test:
	$(PYTHON) -m unittest -v tests/test_mapping.py

verify: test

lock:
	uv pip compile requirements.txt --generate-hashes --output-file requirements.lock

mirror-wheels:
	./install.sh --mirror-wheels

PYTHON ?= python3
TEST_SUITES = tests.test_mapping tests.test_dashboard tests.test_hostile_runtime tests.test_gemini_acp tests.test_acp_lane tests.test_acp_runtime tests.test_broke_acp
UNITTEST_ALL = $(PYTHON) -m unittest -v $(TEST_SUITES)
HOSTILE_TEST = $(PYTHON) -m unittest -v tests.test_hostile_runtime
VERIFY_CHECKS = bash -n bin/broke && $(PYTHON) -m py_compile bin/_acp_lane.py bin/_acp_runtime.py bin/_broke_acp.py bin/_dashboard.py bin/_pty_harness.py bin/_harness_shim.py bin/_mapping.py bin/_gemini_acp.py tests/test_mapping.py tests/test_dashboard.py tests/test_hostile_runtime.py tests/test_gemini_acp.py tests/test_acp_lane.py tests/test_acp_runtime.py tests/test_broke_acp.py

.PHONY: test hostile-test harden verify lock mirror-wheels

test:
	$(UNITTEST_ALL)

hostile-test:
	$(HOSTILE_TEST)

harden: hostile-test

verify: test
	$(VERIFY_CHECKS)

lock:
	uv pip compile requirements.txt --generate-hashes --output-file requirements.lock

mirror-wheels:
	./install.sh --mirror-wheels

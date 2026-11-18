"""Acceptance case evidence is attached to the pytest JUnit report."""
import json
import pytest
from article9.config import Config
from article9.model import initialize


@pytest.fixture(scope="session")
def baseline():
    return Config(), initialize(Config(), 0)


@pytest.fixture
def evidence(request):
    def record(**values):
        request.node.user_properties.append(("evidence", json.dumps(values, sort_keys=True)))
    return record


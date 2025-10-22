from __future__ import annotations
import pytest, respx

@pytest.fixture
def token_getter():
    return lambda: "dummy-token"

@pytest.fixture
def respx_mock():
    with respx.mock(assert_all_called=False) as respx_mgr:
        yield respx_mgr

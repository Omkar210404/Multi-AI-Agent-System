import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.mock import MockProvider
from app.main import create_app
from app.services.search import NullSearchService
from app.services.trace import TraceRecorder


@pytest.fixture
def settings() -> Settings:
    # _env_file=None: tests never read a developer's local .env
    return Settings(_env_file=None, llm_provider="mock", log_level="WARNING")


@pytest.fixture
def mock_llm() -> MockProvider:
    return MockProvider()


@pytest.fixture
def make_client(settings):
    def _make(llm=None, search=None, settings_override: Settings | None = None, **client_kwargs) -> TestClient:
        app = create_app(settings_override or settings, llm=llm, search=search or NullSearchService())
        return TestClient(app, **client_kwargs)
    return _make


@pytest.fixture
def client(make_client, mock_llm) -> TestClient:
    return make_client(llm=mock_llm)


@pytest.fixture
def trace() -> TraceRecorder:
    return TraceRecorder("test-request")

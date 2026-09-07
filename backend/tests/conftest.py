from __future__ import annotations

import os
import tempfile
from pathlib import Path

TEST_TEMP_ROOT = Path(__file__).resolve().parents[2] / ".test-tmp"
TEST_TEMP_ROOT.mkdir(exist_ok=True)
TEST_DATA = Path(tempfile.mkdtemp(prefix="ipcam-tests-", dir=TEST_TEMP_ROOT))
os.environ["IPCAM_DATA_DIR"] = str(TEST_DATA)

import pytest
from fastapi.testclient import TestClient

from app.database.core import Base, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client

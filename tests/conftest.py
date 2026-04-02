"""Shared fixtures for gistfs tests.

Creates a single dedicated gist for the entire test session and cleans it up
at the end.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from gistfs import GistFS


@pytest.fixture(scope="session")
def github_token():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN not set — skipping live tests")
    return token


@pytest.fixture(scope="session")
def test_gist(github_token):
    """Create a dedicated gist for the test session, delete it when done."""
    gfs = GistFS.create(
        description="[gistfs-test] automated test — safe to delete",
        token=github_token,
    )
    yield gfs
    # Cleanup
    gfs.delete_gist()


@pytest.fixture()
def gist_id(test_gist):
    return test_gist.gist_id

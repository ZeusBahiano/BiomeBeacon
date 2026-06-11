import pytest
from aiohttp.test_utils import TestClient, TestServer
from biomebeacon_server.app import create_app
from biomebeacon_server.auth import hash_key
from biomebeacon_server.db import utcnow
from biomebeacon_server.settings import ServerSettings
from mongomock_motor import AsyncMongoMockClient

# Parity vector documented in docs/DATA_MODEL.md (also asserted in bot/tests).
TEST_KEY = "bb_unittest-key-000"
TEST_KEY_HASH = "114198bf7bbb3c482241b2662b531f31891fc92f332308ea433b38a7e113a0bd"
TEST_ADMIN_TOKEN = "bba_bootstrap-token-for-tests"

USER_HEADERS = {"Authorization": f"Bearer {TEST_KEY}"}
ADMIN_HEADERS = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}

VALID_LINK = "https://www.roblox.com/share?code=ab12cd34ef&type=Server"


class FakeDispatcher:
    def __init__(self):
        self.enqueued = []
        self.test_targets = []
        self.test_result = True

    async def start(self):
        pass

    async def stop(self):
        pass

    async def enqueue_event(self, event, user, biome):
        self.enqueued.append((event, user, biome))
        return True

    async def send_test(self, target):
        self.test_targets.append(target)
        return self.test_result


@pytest.fixture
def user_headers():
    return dict(USER_HEADERS)


@pytest.fixture
def admin_headers():
    return dict(ADMIN_HEADERS)


@pytest.fixture
def valid_link():
    return VALID_LINK


@pytest.fixture
def db():
    return AsyncMongoMockClient()["testdb"]


@pytest.fixture
def dispatcher():
    return FakeDispatcher()


@pytest.fixture
async def client(db, dispatcher):
    settings = ServerSettings(
        mongodb_uri="mongodb://unused",
        db_name="testdb",
        host="127.0.0.1",
        port=0,
        server_name="Test Community",
        admin_bootstrap_token=TEST_ADMIN_TOKEN,
        log_level="WARNING",
    )
    app = create_app(settings=settings, db=db, dispatcher=dispatcher)
    test_client = TestClient(TestServer(app))
    await test_client.start_server()
    yield test_client
    await test_client.close()


@pytest.fixture
async def user(db, client):
    """A seeded active user; depends on `client` so init_db has already run."""
    doc = {
        "discord_id": 111,
        "discord_name": "tester",
        "key_hash": hash_key(TEST_KEY),
        "key_prefix": TEST_KEY[:8],
        "private_server_link": VALID_LINK,
        "channel_id": None,
        "webhook_url": None,
        "webhook_broken": False,
        "active": True,
        "created_at": utcnow(),
        "created_by": 1,
        "last_seen": None,
        "last_event_at": None,
        "macro_version": None,
        "roblox_user_ids": [],
    }
    await db.users.insert_one(doc)
    return doc

"""Key hashing parity with the server — vector documented in docs/DATA_MODEL.md."""

import pytest
from biomebeacon_bot.keys import (
    generate_admin_token,
    generate_key,
    hash_key,
    valid_private_server_link,
)

TEST_KEY = "bb_unittest-key-000"
TEST_KEY_HASH = "114198bf7bbb3c482241b2662b531f31891fc92f332308ea433b38a7e113a0bd"


def test_parity_vector_matches_server():
    assert hash_key(TEST_KEY) == TEST_KEY_HASH


def test_generate_key_shape():
    key, key_hash, key_prefix = generate_key()
    assert key.startswith("bb_")
    assert hash_key(key) == key_hash
    assert key_prefix == key[:8]


def test_generate_admin_token_shape():
    token, token_hash, token_prefix = generate_admin_token()
    assert token.startswith("bba_")
    assert hash_key(token) == token_hash
    assert token_prefix == token[:9]


@pytest.mark.parametrize(
    "link",
    [
        "https://www.roblox.com/share?code=ab12cd34ef&type=Server",
        "https://roblox.com/share?code=ABC123&type=Server",
        "https://www.roblox.com/games/15532962292/Sols-RNG?privateServerLinkCode=12345678",
        "https://www.roblox.com/games/15532962292?privateServerLinkCode=ab-cd_12",
    ],
)
def test_valid_links(link):
    assert valid_private_server_link(link)


@pytest.mark.parametrize(
    "link",
    [
        "https://evil.com/share?code=x&type=Server",
        "https://www.roblox.com/games/123",
        "http://www.roblox.com/share?code=x&type=Server",  # not https
        "https://www.roblox.com.evil.com/share?code=x&type=Server",
        "not a link at all",
        "",
    ],
)
def test_invalid_links(link):
    assert not valid_private_server_link(link)

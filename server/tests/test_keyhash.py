"""Key hashing parity with the bot — vector documented in docs/DATA_MODEL.md.

The literals are intentionally duplicated here: this test *is* the contract.
"""

from biomebeacon_server.auth import generate_key, hash_key

TEST_KEY = "bb_unittest-key-000"
TEST_KEY_HASH = "114198bf7bbb3c482241b2662b531f31891fc92f332308ea433b38a7e113a0bd"


def test_parity_vector():
    assert hash_key(TEST_KEY) == TEST_KEY_HASH


def test_generate_key_shape():
    key, key_hash, key_prefix = generate_key()
    assert key.startswith("bb_")
    assert len(key) > 40
    assert hash_key(key) == key_hash
    assert key_prefix == key[:8]
    # two keys never collide
    assert generate_key()[0] != key

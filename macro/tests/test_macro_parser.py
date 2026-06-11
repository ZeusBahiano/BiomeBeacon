"""Parser tests against REAL lines captured from this machine's Roblox logs
(Sol's RNG session, 2026-06-03)."""

from biomebeacon.detection.parser import GameJoin, RpcUpdate, parse_line

REAL_RPC_NORMAL = (
    '2026-06-03T16:02:15.478Z,3.478098,22e8,6 [FLog::Output] [BloxstrapRPC] '
    '{"command":"SetRichPresence","data":{"state":"In Main Menu",'
    '"smallImage":{"hoverText":"Sol\'s RNG","assetId":126196647942405},'
    '"largeImage":{"hoverText":"NORMAL","assetId":80690294537387}}}'
)
REAL_RPC_RAINY = (
    '2026-06-03T16:05:53.569Z,221.569824,22e8,6 [FLog::Output] [BloxstrapRPC] '
    '{"command":"SetRichPresence","data":{"state":"Equipped _None_",'
    '"smallImage":{"hoverText":"Sol\'s RNG","assetId":126196647942405},'
    '"largeImage":{"hoverText":"RAINY","assetId":137992545432987}}}'
)
REAL_JOIN = (
    '2026-06-03T16:02:13.323Z,1.323562,22e8,6 [FLog::GameJoinLoadTime] '
    'Report game_join_loadtime: placeid:15532962292, '
    'join_time:0.57817556300018624338, universeid:5361032378, '
    'referral_page:RequestPrivateGame, sid:a78d8791-f9ca-4a2a-833f-5d21cfa88528, '
    'clienttime:1780502533.256000042, userid:1420234927,'
)


def test_parses_real_rpc_line():
    parsed = parse_line(REAL_RPC_NORMAL)
    assert parsed == RpcUpdate(biome="NORMAL", game="Sol's RNG")
    assert parse_line(REAL_RPC_RAINY) == RpcUpdate(biome="RAINY", game="Sol's RNG")


def test_parses_real_join_line():
    parsed = parse_line(REAL_JOIN)
    assert parsed == GameJoin(place_id=15532962292, roblox_user_id=1420234927)


def test_multiword_biome_uppercased():
    line = REAL_RPC_NORMAL.replace('"NORMAL"', '"Sand Storm"')
    assert parse_line(line).biome == "SAND STORM"


def test_ignores_noise_lines():
    assert parse_line("2026-06-03T16:02:15.000Z,1,22e8,6 [FLog::Output] hello") is None
    assert parse_line("") is None
    assert parse_line("[BloxstrapRPC] not json at all {") is None


def test_ignores_other_rpc_commands():
    line = REAL_RPC_NORMAL.replace("SetRichPresence", "SetLaunchData")
    assert parse_line(line) is None


def test_join_without_userid():
    line = "x [FLog::GameJoinLoadTime] Report game_join_loadtime: placeid:123, join_time:0.5,"
    assert parse_line(line) == GameJoin(place_id=123, roblox_user_id=None)

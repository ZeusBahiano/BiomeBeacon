from biomebeacon.detection.engine import DetectionEngine

RPC = (
    '... [FLog::Output] [BloxstrapRPC] {{"command":"SetRichPresence","data":{{'
    '"state":"x","smallImage":{{"hoverText":"{game}","assetId":1}},'
    '"largeImage":{{"hoverText":"{biome}","assetId":2}}}}}}'
)
JOIN = "... [FLog::GameJoinLoadTime] Report game_join_loadtime: placeid:{place}, userid:{uid},"


def rpc(biome, game="Sol's RNG"):
    return RPC.format(biome=biome, game=game)


def test_first_sighting_emits_started_only():
    engine = DetectionEngine()
    events = engine.process_line("a.log", rpc("NORMAL"), now=10.0)
    assert [(e.biome, e.type) for e in events] == [("NORMAL", "started")]


def test_transition_emits_ended_then_started():
    engine = DetectionEngine()
    engine.process_line("a.log", rpc("NORMAL"), now=10.0)
    events = engine.process_line("a.log", rpc("GLITCHED"), now=20.0)
    assert [(e.biome, e.type) for e in events] == [
        ("NORMAL", "ended"),
        ("GLITCHED", "started"),
    ]


def test_repeated_rpc_is_deduped():
    engine = DetectionEngine()
    engine.process_line("a.log", rpc("RAINY"))
    assert engine.process_line("a.log", rpc("RAINY")) == []
    assert engine.process_line("a.log", rpc("RAINY")) == []


def test_instances_are_independent():
    engine = DetectionEngine()
    engine.process_line("a.log", rpc("NORMAL"))
    events = engine.process_line("b.log", rpc("GLITCHED"))
    assert [(e.biome, e.type) for e in events] == [("GLITCHED", "started")]
    assert engine.instances["a.log"].biome == "NORMAL"
    assert engine.instances["b.log"].biome == "GLITCHED"


def test_join_line_attaches_account_to_events():
    engine = DetectionEngine()
    engine.process_line("a.log", JOIN.format(place=15532962292, uid=1420234927))
    events = engine.process_line("a.log", rpc("HELL"))
    assert events[0].roblox_user_id == 1420234927


def test_other_games_rpc_is_ignored():
    engine = DetectionEngine()
    assert engine.process_line("a.log", rpc("NORMAL", game="Other Game")) == []
    assert engine.instances["a.log"].biome is None


def test_place_filter_gates_unidentified_rpc():
    engine = DetectionEngine(place_ids=[15532962292])
    # RPC without a smallImage game name, before any join: ignored
    line = rpc("NORMAL").replace('"hoverText":"Sol\'s RNG",', '"x":1,')
    assert engine.process_line("a.log", line) == []
    # after joining the right place, the same line counts
    engine.process_line("a.log", JOIN.format(place=15532962292, uid=1))
    assert engine.process_line("a.log", line) != []


def test_drop_instance_emits_nothing_and_forgets():
    engine = DetectionEngine()
    engine.process_line("a.log", rpc("GLITCHED"))
    engine.drop_instance("a.log")
    assert "a.log" not in engine.instances
    # reappearing later is a fresh first sighting
    events = engine.process_line("a.log", rpc("GLITCHED"))
    assert [(e.biome, e.type) for e in events] == [("GLITCHED", "started")]

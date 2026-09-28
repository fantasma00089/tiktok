from repost_monitor.detector import detect_new_reposts
from repost_monitor.models import Repost
from repost_monitor.state import MonitorState


def r(i: str) -> Repost:
    return Repost(item_id=i, url=f"https://www.tiktok.com/@x/video/{i}")


def test_first_run_is_baseline_without_alert():
    state = MonitorState(target="@a")
    assert detect_new_reposts(state, [r("3"), r("2"), r("1")]) == []
    assert state.initialized
    assert state.last_item_id == "3"
    assert state.seen_ids == ["3", "2", "1"]


def test_first_run_can_alert_when_baseline_disabled():
    state = MonitorState(target="@a")
    new = detect_new_reposts(state, [r("1")], baseline_on_first_run=False)
    assert [n.item_id for n in new] == ["1"]
    assert new[0].detected_at


def test_detects_only_unseen_items():
    state = MonitorState(target="@a")
    detect_new_reposts(state, [r("2"), r("1")])
    new = detect_new_reposts(state, [r("4"), r("3"), r("2"), r("1")])
    assert [n.item_id for n in new] == ["4", "3"]
    assert state.last_item_id == "4"
    assert [d["item_id"] for d in state.detections] == ["4", "3"]


def test_empty_response_changes_nothing():
    state = MonitorState(target="@a")
    detect_new_reposts(state, [r("1")])
    assert detect_new_reposts(state, []) == []
    assert state.last_item_id == "1"


def test_profile_without_reposts_alerts_on_first_repost():
    state = MonitorState(target="@a")
    assert detect_new_reposts(state, []) == []  # leitura de base vazia
    assert state.initialized
    assert [n.item_id for n in detect_new_reposts(state, [r("1")])] == ["1"]


def test_undo_repost_does_not_trigger_old_item():
    state = MonitorState(target="@a")
    detect_new_reposts(state, [r("2"), r("1")])
    assert detect_new_reposts(state, [r("1")]) == []  # "2" foi desfeito
    assert detect_new_reposts(state, [r("2"), r("1")]) == []  # voltou: já visto
    assert state.detections == []


def test_seen_ids_are_bounded():
    state = MonitorState(target="@a")
    detect_new_reposts(state, [r(str(i)) for i in range(10)], max_seen_ids=5)
    assert len(state.seen_ids) == 5

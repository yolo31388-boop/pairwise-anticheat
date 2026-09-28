
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from anticheat.system import AntiCheat


def test_speed_threshold_by_state():
    ac = AntiCheat()
    ac.player_positions["p1"] = (0, 0)
    # 坐骑状态下速度阈值更高
    assert ac.check_speed("p1", (0, 15), 1, state="mount") == False
    ac.player_positions["p1"] = (0, 0)
    assert ac.check_speed("p1", (0, 15), 1, state="walk") == True


def test_sweep_wallhack_detection():
    ac = AntiCheat()
    walls = [(5, -5, 10, 5)]  # x从5到10，y从-5到5
    assert ac.check_wallhack("p1", (0, 0), (15, 0), walls) == True


def test_autofarm_multidimensional():
    ac = AntiCheat()
    # 手速快但模式正常不应被封
    normal_actions = [{"type": "click", "reaction_time": 0.3} for _ in range(50)]
    assert ac.check_autofarm("p1", normal_actions) == False


def test_multibox_device_fingerprint():
    ac = AntiCheat()
    players = [
        {"ip": "1.1.1.1", "device_id": "dev1"},
        {"ip": "1.1.1.1", "device_id": "dev2"},
    ]
    assert ac.check_multibox(players) == False


def test_report_weight_system():
    ac = AntiCheat()
    ac.report_weights["newbie"] = 0
    ac.report_weights["veteran"] = 10
    # 低权重举报不应直接封号
    ac.process_report("newbie", "target1")
    assert "target1" not in ac.bans


def test_high_weight_report_bans():
    ac = AntiCheat()
    ac.report_weights["veteran"] = 10
    ac.process_report("veteran", "target2")
    assert "target2" in ac.bans


def test_speed_tolerance():
    ac = AntiCheat()
    ac.player_positions["p1"] = (0, 0)
    # 略微超过阈值但在容差内
    assert ac.check_speed("p1", (0, 10.5), 1, state="walk") == False


def test_data_validation_runtime():
    ac = AntiCheat()
    ac.player_data["p1"] = {"hp": 100}
    ac.validate_runtime("p1", {"hp": 9999})
    assert ac.flagged.get("p1") == True


def test_no_false_positive_normal_play():
    ac = AntiCheat()
    ac.player_positions["p1"] = (0, 0)
    walls = []
    assert ac.check_speed("p1", (0, 5), 1, state="walk") == False
    assert ac.check_wallhack("p1", (0, 0), (5, 0), walls) == False

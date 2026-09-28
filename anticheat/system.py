
class AntiCheat:
    def __init__(self):
        self.player_positions = {}
        self.bans = set()
        self.report_weights = {}

    def check_speed(self, pid, new_pos, dt, state="walk"):
        # BUG: 固定阈值
        old = self.player_positions.get(pid, new_pos)
        dist = ((new_pos[0]-old[0])**2 + (new_pos[1]-old[1])**2)**0.5
        speed = dist / max(dt, 0.001)
        self.player_positions[pid] = new_pos
        return speed > 10

    def check_wallhack(self, pid, old_pos, new_pos, walls):
        # BUG: 只看终点
        for w in walls:
            if self._point_in_rect(new_pos, w):
                return True
        return False

    def check_autofarm(self, pid, actions):
        # BUG: 只看频率
        return len(actions) > 100

    def check_multibox(self, players):
        # BUG: 只看IP
        ips = set()
        for p in players:
            if p["ip"] in ips:
                return True
            ips.add(p["ip"])
        return False

    def process_report(self, reporter, target):
        # BUG: 举报无权重
        if target not in self.bans:
            self.bans.add(target)
        return True

    def _point_in_rect(self, pos, rect):
        return rect[0] <= pos[0] <= rect[2] and rect[1] <= pos[1] <= rect[3]

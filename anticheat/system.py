class AntiCheat:
    # 各状态基础速度阈值与容差（容差用于吸收网络抖动/帧率误差）
    SPEED_LIMITS = {"walk": 10.0, "mount": 20.0, "skill": 30.0}
    SPEED_TOLERANCE = 1.0
    # 举报权重达到该值才封号
    REPORT_BAN_THRESHOLD = 5.0
    # 运行时数据校验允许的偏差倍数
    DATA_TOLERANCE_RATIO = 5.0

    def __init__(self):
        self.player_positions = {}
        self.bans = set()
        self.report_weights = {}
        self.report_totals = {}
        self.player_data = {}
        self.flagged = {}
        self.pending_reverify = {}

    def check_speed(self, pid, new_pos, dt, state="walk"):
        # 按玩家状态（步行/坐骑/技能）使用动态阈值，并保留容差
        old = self.player_positions.get(pid, new_pos)
        dist = ((new_pos[0] - old[0]) ** 2 + (new_pos[1] - old[1]) ** 2) ** 0.5
        speed = dist / max(dt, 0.001)
        self.player_positions[pid] = new_pos
        limit = self.SPEED_LIMITS.get(state, self.SPEED_LIMITS["walk"])
        return speed > limit + self.SPEED_TOLERANCE

    def check_wallhack(self, pid, old_pos, new_pos, walls):
        # 扫掠检测：沿移动路径做线段-矩形相交测试，而非只看终点
        for w in walls:
            if self._segment_intersects_rect(old_pos, new_pos, w):
                return True
        return False

    def check_autofarm(self, pid, actions):
        # 多维度检测：操作模式 + 反应时间 + 路径分析，不只看频率
        if not actions:
            return False
        reaction_times = [a.get("reaction_time") for a in actions
                          if a.get("reaction_time") is not None]
        inhuman_reactions = 0
        if reaction_times:
            # 反应时间低于人类极限（<0.1s）的比例
            inhuman = sum(1 for t in reaction_times if t < 0.1)
            inhuman_reactions = inhuman / len(reaction_times)
            # 反应时间方差趋近于 0 说明是机器固定节拍
            mean = sum(reaction_times) / len(reaction_times)
            variance = sum((t - mean) ** 2 for t in reaction_times) / len(reaction_times)
            machine_like_tempo = variance < 1e-6 and len(reaction_times) > 10
        else:
            machine_like_tempo = False
        # 操作模式：完全无操作类型变化
        types = {a.get("type") for a in actions}
        monotone_pattern = len(types) <= 1 and len(actions) > 200
        # 路径分析：所有移动目标点完全一致
        targets = {(a.get("x"), a.get("y")) for a in actions
                   if a.get("x") is not None and a.get("y") is not None}
        fixed_path = len(targets) == 1 and len(actions) > 50
        signals = sum([
            inhuman_reactions > 0.5,
            machine_like_tempo and inhuman_reactions > 0,
            monotone_pattern,
            fixed_path,
        ])
        return signals >= 2

    def check_multibox(self, players):
        # 设备指纹 + 行为特征综合判定，IP 只作参考（网吧同 IP 不误判）
        devices = {}
        for p in players:
            dev = p.get("device_id")
            if not dev:
                continue
            if dev in devices:
                return True
            devices[dev] = p
        # 同 IP 且行为特征高度一致（如相同行为签名）才算可疑
        ip_groups = {}
        for p in players:
            ip_groups.setdefault(p.get("ip"), []).append(p)
        for group in ip_groups.values():
            if len(group) < 2:
                continue
            behaviors = [p.get("behavior_sig") for p in group]
            if all(b is not None for b in behaviors) and len(set(behaviors)) == 1:
                return True
        return False

    def validate_runtime(self, pid, current_data):
        # 游戏中定时校验关键数据，异常时标记并触发二次验证
        baseline = self.player_data.get(pid)
        if baseline is None:
            self.player_data[pid] = dict(current_data)
            return False
        abnormal = False
        for key, value in current_data.items():
            base = baseline.get(key)
            if isinstance(base, (int, float)) and isinstance(value, (int, float)):
                limit = max(abs(base) * self.DATA_TOLERANCE_RATIO, 1.0)
                if abs(value - base) > limit:
                    abnormal = True
            elif value != base:
                abnormal = True
        if abnormal:
            self.flagged[pid] = True
            self.pending_reverify[pid] = dict(current_data)
            return True
        self.player_data[pid] = dict(current_data)
        return False

    def process_report(self, reporter, target):
        # 举报按权重累计（账号等级/历史信誉），低权重举报不计入
        weight = self.report_weights.get(reporter, 1)
        if weight <= 0:
            return False
        total = self.report_totals.get(target, 0) + weight
        self.report_totals[target] = total
        if total >= self.REPORT_BAN_THRESHOLD:
            self.bans.add(target)
            return True
        return False

    def _point_in_rect(self, pos, rect):
        return rect[0] <= pos[0] <= rect[2] and rect[1] <= pos[1] <= rect[3]

    def _segment_intersects_rect(self, p1, p2, rect):
        if self._point_in_rect(p1, rect) or self._point_in_rect(p2, rect):
            return True
        x1, y1, x2, y2 = rect
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        edges = [(corners[i], corners[(i + 1) % 4]) for i in range(4)]
        return any(self._segments_intersect(p1, p2, a, b) for a, b in edges)

    def _segments_intersect(self, p1, p2, p3, p4):
        def cross(o, a, b):
            return ((a[0] - o[0]) * (b[1] - o[1])
                    - (a[1] - o[1]) * (b[0] - o[0]))
        d1 = cross(p3, p4, p1)
        d2 = cross(p3, p4, p2)
        d3 = cross(p1, p2, p3)
        d4 = cross(p1, p2, p4)
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
            return True
        def on_segment(a, b, p):
            return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
                    and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))
        if d1 == 0 and on_segment(p3, p4, p1):
            return True
        if d2 == 0 and on_segment(p3, p4, p2):
            return True
        if d3 == 0 and on_segment(p1, p2, p3):
            return True
        if d4 == 0 and on_segment(p1, p2, p4):
            return True
        return False

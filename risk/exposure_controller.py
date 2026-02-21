class ExposureController:
    def __init__(self, max_directional=3, max_margin_usage=0.4):
        self.max_directional = max_directional
        self.max_margin_usage = max_margin_usage

    def directional_allowed(self, open_positions, new_signal):
        same_side = [
            p for p in open_positions
            if p["side"] == new_signal["side"]
        ]
        return len(same_side) < self.max_directional

    def margin_allowed(self, equity, used_margin):
        if equity == 0:
            return False
        return (used_margin / equity) < self.max_margin_usage

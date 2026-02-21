class LosingStreakGuard:
    def __init__(self, max_losses=5):
        self.consecutive_losses = 0
        self.max_losses = max_losses

    def register_trade(self, pnl):
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    @property
    def blocked(self):
        return self.consecutive_losses >= self.max_losses

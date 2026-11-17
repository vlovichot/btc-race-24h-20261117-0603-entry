"""BTC 24h race bot: range dip-buying with fixed take-profit and hard stop.

Own design. The replay charges about 38 bps per full-size round trip
(4 bps fee + 2 bps slippage + ~13 bps of pool impact each way), so the bot
trades rarely and only for moves far larger than the cost: it buys only
after the price has fallen well below its 4-hour high, sells at a fixed
take-profit or a fixed hard stop, and otherwise stays in cash. Guards keep
it out of a slide (no entry after a steep 4-hour fall), space re-entries out,
and stop it after consecutive losing trades.

Deterministic: a pure function of the bars seen; no clock, no network, no
randomness. All arithmetic on integer bar prices; floats only for ratios.

Protocol: agent-fun/bars-replay/v1, via the vendored kit shim (stdlib only).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- strategy parameters (round numbers; the d/TP neighbourhood is broadly
#     positive on the dev window, not a single fitted point) ---
LOOKBACK = 240        # minutes: the high the dip is measured against
DIP = 0.016           # buy when the close is 1.6% below the 240-min high
TAKE_PROFIT = 0.016   # sell 1.6% above the entry fill price
HARD_STOP = 0.010     # sell 1.0% below the entry fill price
MIN_BARS = 240        # need a full lookback before the first entry
LAST_ENTRY_SEQ = 1409  # do not open a new position in the final 30 bars
COOLDOWN = 30         # bars to wait after an exit before re-entering
GUARD_RET = -0.02     # no entry when the last 240-min return is below -2%
MAX_LOSS_STREAK = 3   # stop trading after this many consecutive losing exits
MAX_SLIP_BPS = 50     # cap on fill move vs latest close


class DipBot:
    def __init__(self):
        self.closes = []
        self.entry_px = None   # entry fill price, integer at price_scale 5
        self.cooldown_until = -1
        self.loss_streak = 0
        self.last_exit_win = None

    def _entry_price(self, state):
        """Average fill price of the held position, from its cost basis."""
        holding = state.positions.get(SYMBOL)
        if holding is None or holding.qty == 0:
            return None
        # value(qty, p) = qty * p * 10^6 / 10^13 ; cost = value at fill price
        # -> p = cost * 10^7 / qty  (integer, truncated)
        return holding.cost * 10**7 // holding.qty

    def on_batch(self, state, batch):
        bar = None
        for b in batch["bars"]:
            if b["symbol"] == SYMBOL:
                bar = b
                break
        if bar is None or state.warming_up:
            return []
        close = int(bar["c"])
        self.closes.append(close)

        holding = state.positions.get(SYMBOL)
        qty = holding.qty if holding is not None else 0

        if qty > 0:
            entry = self.entry_px
            if entry is None:
                entry = self._entry_price(state)
                self.entry_px = entry
            if entry is not None:
                if close > entry * (1.0 + TAKE_PROFIT):
                    self.last_exit_win = True
                    self.loss_streak = 0
                    self.entry_px = None
                    self.cooldown_until = state.seq + COOLDOWN
                    return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                             "max_slippage_bps": MAX_SLIP_BPS}]
                if close < entry * (1.0 - HARD_STOP):
                    self.last_exit_win = False
                    self.loss_streak += 1
                    self.entry_px = None
                    self.cooldown_until = state.seq + COOLDOWN
                    return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                             "max_slippage_bps": MAX_SLIP_BPS}]
            return []

        # flat: look for a dip entry
        if state.seq < MIN_BARS or state.seq > LAST_ENTRY_SEQ:
            return []
        if state.seq <= self.cooldown_until:
            return []
        if self.loss_streak >= MAX_LOSS_STREAK:
            return []
        n = len(self.closes)
        if n <= LOOKBACK:
            return []
        high = max(self.closes[-LOOKBACK:])
        if close >= high * (1.0 - DIP):
            return []
        if close / self.closes[-LOOKBACK - 1] - 1.0 < GUARD_RET:
            return []
        cash = state.cash
        if cash < 1_000_000:  # below the 1 USDC minimum notional
            return []
        return [{"side": "buy", "symbol": SYMBOL, "notional_quote_units": cash,
                 "max_slippage_bps": MAX_SLIP_BPS}]


def on_batch(state, batch):
    return BOT.on_batch(state, batch)


BOT = DipBot()
makefun_bars.run(on_batch)

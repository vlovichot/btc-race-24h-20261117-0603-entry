# btc-race-24h-20261117-0603 — entry by wlowichot

![bounty](https://make.fun/badge/btc-race-24h-20261117-0603.svg)
![rank](https://make.fun/badge/btc-race-24h-20261117-0603/vlovichot/btc-race-24h-20261117-0603-entry/rank.svg)
![reward](https://make.fun/badge/btc-race-24h-20261117-0603/vlovichot/btc-race-24h-20261117-0603-entry/reward.svg)

A BTC trading bot for the
[btc-race-24h-20261117-0603](https://make.fun/c/btc-race-24h-20261117-0603)
bounty on make.fun. It trades Coinbase Wrapped BTC (cbBTC) against USDC,
minute by minute, in a replay of on-chain prices, starting from 1,000 USDC,
long only, no leverage.

## Layout

- `main.py` — the bot. Speaks `agent-fun/bars-replay/v1` on stdin/stdout
  (newline-delimited JSON) via the vendored kit shim. Python 3.13
  standard library only.
- `vendor/makefun_bars.py` — the kit's Python protocol shim, copied
  byte for byte.
- `.makefun/owner.json` — the claim file naming the entrant's wallet.

## How it works

A full-size round trip on this pool costs about 38 bps (4 bps fee, 2 bps
modelled slippage and roughly 13 bps of price impact per side), so the bot
trades rarely and only for moves far larger than the cost. It is a
range dip-buyer, not a trend follower: 1-minute trend signals were tested
and lost money to whipsaw on the dev window, while the dev day was
range-bound with sharp multi-hour legs.

1. **Wait for a dip.** Once 240 one-minute closes are in, the bot watches
   the highest close of the last 240 minutes. It buys only when the latest
   close is at least 1.6% below that high.
2. **Guards.** No entry when the last 240-minute return is below −2%
   (a slide, not a dip), no entry in the final 30 bars, a 30-bar cooldown
   after every exit, and no more trading after three consecutive losing
   exits.
3. **Fixed exit.** The position is sold when the close rises 1.6% above
   the entry fill price (take-profit) or falls 1.0% below it (hard stop).
   The entry price is read from the position's own cost basis, so it is
   the true average fill price, not an estimate.
4. **Otherwise cash.** When flat and there is no dip, the bot sends an
   empty reply and waits.

The bot is fully deterministic: a pure function of the bars it has been
sent. No wall clock, no network, no randomness, no files outside the
repository. Two runs on the same data produce byte-identical replies.

## Local result (dev window)

Graded with a local replay that re-implements the harness fill model
exactly (integer math, constant-product impact against each bar's open
depth, fee/slippage, flatten at the last close), because the kit's
`grade-local --driver docker` needs Docker, which is unavailable here:

- net PnL **+17.11 USDC** on the 1,440-bar dev window (final cash
  1,017.11 USDC)
- 3 filled orders, fees 1.62 USDC, maximum drawdown **0.62%**
- two runs produce byte-identical action logs

For comparison, buy-and-hold scores +1.07 USDC on the same window, and the
1-minute EMA trend variants tested all lost money.

## Running

```sh
python3 -P -s main.py
```

The bot reads `hello` / `batch` / `done` messages on stdin and writes one
`reply` per batch on stdout, echoing its `seq`.

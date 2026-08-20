# Brain
LLM AGENT

## Aristotle Alert System

A watchlist scanner and open-position manager built around the Aristotle
Investments / "Trading Bondsman" framework: top-down multi-timeframe
analysis, RSI/MACD divergence, 8/21/200 EMA structure, Fibonacci golden
pocket, pin bar / engulfing detection, the 15-cent entry rule, and
R-multiple scale-out position management.

**This script does not place trades.** It only reads market data (via
[yfinance](https://github.com/ranaroussi/yfinance)) and prints/logs
alerts. You still pull the trigger — that's intentional. Alerting is
where automation earns its keep; execution is where a coded
pattern-match can quietly cost you real money if it's wrong.

### Install

```bash
pip install -r requirements.txt
```

### Configure

Copy the example config and edit it with your real watchlist and
positions:

```bash
cp config.example.json config.json
```

```json
{
  "watchlist": ["SPY", "QQQ", "TSLA"],
  "positions": {
    "TSLA": {
      "entry": 250.00,
      "stop": 235.00,
      "shares": 30,
      "targets": [[1.0, 0.33], [2.0, 0.33]],
      "trail_after_R": 2.0,
      "trail_method": "21ema"
    }
  }
}
```

- `entry` / `stop` — your average entry price and structural stop-loss.
- `shares` — how many shares/contracts you currently hold.
- `targets` — list of `[R-multiple, fraction_of_ORIGINAL_position_to_sell]`.
  `[1.0, 0.33]` means "at 1R profit, sell 33% of the original size."
- `trail_after_R` — once price passes this R-multiple, the remaining size
  switches to a trailing-stop suggestion instead of a fixed target.
- `trail_method` — `"21ema"`, `"8ema"`, or `"swing_low"` (10-candle low).

`config.json` is gitignored so your real entries/stops never end up in
version control. If no `--config` file is found, the script falls back to
the `WATCHLIST` / `POSITIONS` constants at the top of
`aristotle_alert_system.py`.

### Run

```bash
python aristotle_alert_system.py --config config.json
```

Useful flags (all optional, see `--help`):

| Flag | Env var | Default | Purpose |
|---|---|---|---|
| `--config` | `ARISTOTLE_CONFIG` | `config.json` | Watchlist/positions file |
| `--log-file` | `ARISTOTLE_LOG_FILE` | `alerts.log` | Rotating log file (5 x 2MB); pass `""` to disable |
| `--webhook-url` | `ARISTOTLE_WEBHOOK_URL` | *(none)* | Slack or Discord incoming webhook for a summary of important alerts |
| `--quiet` | | off | Suppress console output, log to file only |

Every run appends to the rotating log file regardless of how it's
invoked, so a cron run's history survives even if you don't redirect
stdout yourself.

### Alerting

Set a Slack or Discord **incoming webhook URL** and the script will push a
one-message summary of anything important from the run (confluence
alerts, stop-loss hits, target hits, trailing-stop updates):

```bash
export ARISTOTLE_WEBHOOK_URL="https://hooks.slack.com/services/..."
python aristotle_alert_system.py --config config.json
```

Discord webhooks (URLs containing `discord.com`) are auto-detected and
sent in Discord's payload format; anything else is sent as a Slack-style
`{"text": ...}` payload, which most other chat webhook receivers also
accept.

### Running on a schedule

This script is the brain; a scheduler is the heartbeat. It does not loop
or schedule itself — wire it into cron (or an equivalent) to run
automatically, e.g. 8:00am and 3:30pm ET on weekdays:

```cron
# crontab -e
0 8  * * 1-5 cd /path/to/Brain && /usr/bin/python3 aristotle_alert_system.py --config config.json >> cron.log 2>&1
30 15 * * 1-5 cd /path/to/Brain && /usr/bin/python3 aristotle_alert_system.py --config config.json >> cron.log 2>&1
```

Or as a systemd timer/service (`aristotle-alert.service` +
`aristotle-alert.timer` with `OnCalendar=Mon..Fri 08:00,15:30`), or a
macOS `launchd` plist with matching `StartCalendarInterval` entries.

### Reliability notes

- **Network retries:** every data fetch retries up to 3 times with
  exponential backoff before giving up on that timeframe/ticker. A
  single bad request never crashes the run.
- **Fault isolation:** a failure scanning one timeframe (e.g. Weekly)
  does not stop the Daily/4-Hour scan for that ticker, and a failure on
  one ticker does not stop the rest of the watchlist or the position
  check.
- **RSI edge case:** a plain `avg_gain / avg_loss` RSI formula returns
  `NaN` whenever a lookback window has zero down-days (i.e. a strong,
  clean uptrend) — exactly when you most want a reading. This is handled
  explicitly (all-up window → RSI 100, all-flat window → RSI 50) instead
  of silently emitting `nan`.
- **Divergence detection:** in addition to the candlestick patterns, the
  scanner flags simple RSI/MACD-histogram divergence — the most recent
  candle sets a new price extreme that the indicator fails to confirm.
  This is a cheap single-candle-vs-recent-extreme heuristic, not full
  swing-to-swing divergence — validate against your own chart reading.

### Testing

```bash
pip install -r requirements-dev.txt
pytest
```

The test suite covers the indicator math (EMA/RSI/MACD/Fibonacci),
candlestick pattern detection, divergence detection, position
scale-out/stop/trailing logic (as pure, network-free functions), the
fetch retry/backoff/MultiIndex-column handling, config loading, and
webhook notification formatting — all without hitting the network.

## MCP Server

`mcp_server.py` wraps this repo's scan/position/risk logic as [MCP](https://modelcontextprotocol.io)
tools, so an MCP client (Claude Desktop, an agent session, the MCP
inspector) can call it directly instead of shelling out to the scripts. It
adds no new trading logic and places no orders -- it's a thin adapter over
the already-tested functions in `aristotle_alert_system.py`,
`robinhood_scan.py`, and `robinhood_risk.py`.

Tools exposed:

| Tool | Wraps | Network? |
|---|---|---|
| `scan_ticker` | `aristotle_alert_system.scan_ticker` | yes (yfinance) |
| `check_position` | `aristotle_alert_system.evaluate_position` | yes (yfinance) |
| `run_watchlist_scan` | full watchlist + position scan | yes (yfinance) |
| `evaluate_confluence` | `robinhood_scan.evaluate` | no (caller supplies bars) |
| `size_position` | `robinhood_risk.position_size` | no |
| `check_daily_caps` | `robinhood_risk.daily_caps_ok` | no |
| `get_config` | `aristotle_alert_system.load_config` | no |

### Run

```bash
pip install -r requirements.txt
```

Test interactively with the MCP inspector:

```bash
mcp dev mcp_server.py
```

Or run it directly over stdio for a real MCP client config (e.g. Claude
Desktop's `claude_desktop_config.json`):

```bash
python mcp_server.py
```

### Disclaimer

Every heuristic here (candlestick patterns, divergence, golden pocket,
trend/RSI state) is a pattern-match on historical price data, not a
guarantee. Nothing in this repository is financial advice, and the
script places no trades — confirm every signal yourself before acting on
it.

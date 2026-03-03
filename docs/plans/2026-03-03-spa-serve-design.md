# Design: `spa serve` Command

## Goal

Add `uv run spa serve` to replace the manual `cd web && python3 -m http.server 8000` workflow.

## Interface

```
uv run spa serve [--port 8000] [--no-open]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | 8000 | Starting port to try |
| `--no-open` | false | Skip auto-opening browser |

## Startup Sequence

1. Check `web/data/analysis.json` exists - exit with helpful message if not
2. Find free port: try requested port, increment by 1 up to 10 attempts
3. Start `http.server.HTTPServer` serving `web/` directory
4. Register SIGINT/SIGTERM handler for clean shutdown
5. Print `Serving at http://localhost:<port>  (Ctrl+C to stop)`
6. Call `webbrowser.open(url)` unless `--no-open`
7. Block on `serve_forever()`

## Shutdown

SIGINT triggers `server.shutdown()` and a clean exit message. Port is released immediately.

## Out of Scope

- Live reload on `analysis.json` changes
- Custom bind address (localhost only)
- Browser-tab-close detection (not feasible with a static server)
- Running the pipeline before serving (use `spa && spa serve`)

## Implementation Notes

- New `@app.command()` in `cli.py` - no new files needed
- Port finding: `socket.bind()` probe, no extra deps
- Browser open: `webbrowser.open()` from stdlib
- Serving `web/` relative to project root (same as `WEB_DATA_DIR` parent)

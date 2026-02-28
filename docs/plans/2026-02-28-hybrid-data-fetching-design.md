# Hybrid Data Fetching with Incremental Processing

**Date:** 2026-02-28
**Status:** Design approved, ready for implementation

## Problem

Current architecture uses a git submodule for the data source (`x1xhlol/system-prompts-and-models-of-ai-tools`). This creates friction:
- Confusing for new users (submodule setup steps)
- Makes sharing harder (recipients must understand submodules)
- Reprocesses all 26 prompts on every run, wasting LLM tokens (~$2-3 per run on GPT-4)

## Solution

Replace git submodule with GitHub API fetching + incremental processing:
1. Fetch data on-demand from upstream GitHub repo
2. Cache LLM analysis results in `analysis.json`
3. Only reprocess files that changed since last run
4. Skip entirely if no upstream changes (unless `--force`)

**Token savings:** ~85% for typical updates (3-5 files changed)

## Architecture

### Data Source Module

Create `src/spa/data_source.py`:
- `fetch_upstream_data()` - Download/update files from GitHub API
- `get_current_commit()` - Check latest upstream commit SHA
- `get_cached_commit()` - Read cached commit from metadata
- `detect_changed_files(old_commit, new_commit)` - Return list of changed paths

### Metadata File

`.spa-data-source.json` (gitignored):
```json
{
  "upstream_repo": "x1xhlol/system-prompts-and-models-of-ai-tools",
  "commit": "abc123...",
  "fetched_at": "2026-02-28T10:00:00Z",
  "file_hashes": {
    "claude-code/current.txt": "sha256:...",
    "cursor/gpt4.txt": "sha256:..."
  }
}
```

### Extended analysis.json

Add cache metadata to output:
```json
{
  "generated_at": "...",
  "cache_info": {
    "data_source_commit": "abc123",
    "file_hashes": {
      "claude-code/current.txt": "sha256:...",
      ...
    }
  },
  "meta": {...},
  "prompts": [...]
}
```

## Incremental Processing Logic

For each prompt in `agents.yaml`:
1. Compute SHA256 hash of the prompt file
2. Check if hash exists in previous `analysis.json` cache
3. **If hash matches:** Reuse `llm_analysis` from cache, recompute rule-based metrics (fast)
4. **If hash differs or no cache:** Full processing (parse + metrics + LLM)

**Why recompute rule-based metrics?**
- Fast (milliseconds per file)
- Ensures metrics never stale if formulas change
- Only LLM analysis is expensive enough to cache

**Cache invalidation:**
- `agents.yaml` changes → invalidate entire cache (can't map old results to new structure)
- Missing/corrupted cache files → treat as cache miss, full reprocessing

## CLI Interface

### New Flags

```bash
uv run spa                    # Default: check for updates, use cache
uv run spa --force            # Reprocess everything, ignore cache
uv run spa --update-data      # Force fetch latest data from upstream
uv run spa --skip-update      # Don't check upstream, use local data
uv run spa --skip-llm         # Existing: skip LLM analysis (rule-based only)
```

**TODO:** Consider migrating from `argparse` to `typer` for better UX (auto-completion, validation).

### Behavior Matrix

| Flags | Data fetch | Change detection | LLM cache |
|-------|-----------|-----------------|----------|
| (none) | Check upstream | Yes | Use cache |
| `--force` | Fetch latest | Skip | Ignore cache |
| `--update-data` | Fetch latest | Yes | Use cache |
| `--skip-update` | Skip | No | Use cache |
| `--skip-llm` | Check upstream | Yes | N/A |

### Example Output

```bash
$ uv run spa
Checking upstream for updates...
✓ Data up to date (commit abc123, 26 files)
Using cached LLM results for 14 unchanged prompts
Running LLM analysis on 3 changed prompts...
...

$ uv run spa --force
Fetching latest data...
✓ Downloaded 26 files (commit def456)
Reprocessing all prompts (forced)...
Running LLM analysis on 17 prompts...
...
```

## Error Handling

### GitHub API Failures
- Network errors, rate limits, API downtime
- **Behavior:**
  1. Check if recent `analysis.json` exists
  2. Prompt: "Can't check for updates (network error). Existing analysis is from 2 days ago. Use it? [Y/n]"
  3. If Yes → exit without reprocessing (existing analysis is fine)
  4. If No → ask: "Reprocess with current local data? [y/N]"
- If no existing `analysis.json`, exit with error

### Corrupted Cache
- Malformed `.spa-data-source.json` or invalid `analysis.json`
- **Behavior:** Treat as cache miss, full reprocessing
- **Message:** "Cache invalid, performing full analysis..."

### Missing Data Directory
- `data/` doesn't exist or is empty
- **Behavior:** Auto-fetch with confirmation prompt
- **Message:** "Data directory not found. Fetch from upstream? [Y/n]"

### Partial Data Updates
- Some files fail to download during `--update-data`
- **Behavior:** Track successes/failures, warn about incompleteness
- **Message:** "Warning: 2 files failed to download. Analysis may be incomplete. Retry with --force."

### agents.yaml Changes
- New assistants added, paths changed, entries removed
- **Behavior:** Invalidate entire cache
- **Message:** "agents.yaml changed, performing full analysis..."

### LLM API Failures
- Some prompts fail analysis (rate limit, timeout, validation error)
- **Behavior:** Continue processing others, mark failed as `llm_analysis: null`
- **Message:** "LLM analysis failed for 2 prompts (see logs). Continuing with remaining..."

**All errors logged to `spa.log` for debugging.**

## Migration Path

### Transition Steps

1. **Create new branch:** `feature/hybrid-data-fetching`
2. **Remove submodule:**
   ```bash
   git rm data
   git commit -m "Remove data submodule"
   ```
3. **Add to .gitignore:**
   ```
   data/
   .spa-data-source.json
   ```
4. **First-run experience:**
   - Pipeline detects missing `data/`, prompts for fetch
   - Downloads all files, creates `.spa-data-source.json`

### Documentation Updates

- **README:** Remove submodule steps, document new flags
- **CLAUDE.md:** Remove submodule workflow, add data management commands
- Add section on data source and privacy

### Backward Compatibility

- None needed - clean break is simpler
- Old branches with submodule continue to work independently
- Can revert merge if hybrid approach causes issues

## Testing Strategy

### Unit Tests

**`tests/test_data_source.py`:**
- `test_detect_changed_files()` - Correct diff between commits
- `test_compute_file_hash()` - SHA256 deterministic
- `test_get_cached_commit_missing_file()` - Returns None gracefully
- `test_fetch_upstream_data_mocked()` - Mock GitHub API, verify downloads

**`tests/test_incremental.py`:**
- `test_cache_hit_reuses_llm_analysis()` - Hash match reuses analysis
- `test_cache_miss_triggers_llm()` - Hash differ runs LLM
- `test_agents_yaml_change_invalidates_cache()` - Full reprocess on config change
- `test_partial_cache_mixed_processing()` - Mixed cached/new prompts merge correctly

### Integration Tests

**`tests/test_pipeline_incremental.py`:**
- `test_full_pipeline_no_changes()` - Second run skips with no changes
- `test_full_pipeline_with_changes()` - One file changed, only it gets LLM
- `test_force_flag_ignores_cache()` - `--force` reprocesses everything

### Mocking

- Use `responses` library for GitHub API mocks
- Fixtures: sample prompts in `tests/fixtures/sample-data/`
- Mock `.spa-data-source.json` and previous `analysis.json`

## Implementation Phases

1. **Data source module** - GitHub API fetching, caching logic
2. **Incremental processing** - Hash computation, cache lookup, merge logic
3. **CLI integration** - New flags, behavior matrix
4. **Error handling** - All failure modes covered
5. **Testing** - Full test coverage
6. **Migration** - Remove submodule, update docs
7. **Verification** - Manual testing with real upstream updates

## Benefits

- **Simpler sharing:** Just clone and run, no submodule confusion
- **Cost savings:** ~85% reduction in LLM tokens for typical updates
- **Better UX:** Clear messages, automatic data fetching
- **Maintainable:** Clean separation of concerns, well-tested
- **Flexible:** Multiple flags for different workflows (offline, force, etc.)

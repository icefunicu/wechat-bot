# Repository Guidelines

## Project Structure & Module Organization
- `run.py`: Unified entry point (start/check/setup).
- `requirements.txt`: Runtime dependencies.
- `app/`: Main application package.
  - `bot.py`: Main `WeChatBot` class controlling the lifecycle.
  - `main.py`: Async entry point initializing the bot.
  - `config.py`: Runtime configuration logic.
  - `core/`: Core business logic (AI client, Memory, Factory, Emotion).
  - `handlers/`: Message processing handlers (Filter, Sender, Converters).
  - `utils/`: General utilities (Logging, Config loader, Common tools).
- `tools/`: Standalone tools.
  - `chat_exporter/`: CSV export logic.
  - `prompt_gen/`: Personalized prompt generator.
  - `wx_db/`: WeChat database interface.
- `data/`: Data directory (API keys, databases - gitignored).
- `scripts/`: Maintenance scripts (setup, check).
- `wxauto_logs/`: Runtime logs.

## Build, Test, and Development Commands
- `pip install -r requirements.txt`: install dependencies.
- `pip install -r requirements.txt`: install dependencies.
- `python run.py start`: run the bot.
- `python run.py check`: check environment and dependencies.
- `python run.py setup`: run configuration wizard.
- `python -m unittest discover -s tests`: run unit tests.
- The app targets Windows + WeChat PC 3.9.x (4.x not supported). Keep the client logged in and running.
- `app/config.py` changes are polled and hot-reloaded; logic changes require a restart.

## Configuration Notes
- `api`: supports `presets` + `active_preset`; `base_url`/`model`/`api_key`, timeouts, retries, `temperature`, `max_tokens`/`max_completion_tokens`, and optional `reasoning_effort`.
- `bot`: reply suffix, emoji policy (`wechat`/`strip`/`keep`/`mixed`), context/history limits, polling/delay settings, keepalive/reconnect, group reply rules (`self_name`, `group_reply_only_when_at`, `whitelist`, ignore lists), and send fallbacks.
- `bot` (personalization): `personalization_enabled`, `profile_update_frequency`, `remember_facts_enabled`, `max_context_facts`, `profile_inject_in_prompt`.
- `bot` (emotion): `emotion_detection_enabled`, `emotion_detection_mode` (keywords/ai), `emotion_inject_in_prompt`, `emotion_log_enabled`.
- `logging`: level/file/rotation (`wxauto_logs/bot.log` by default).

## Implemented Features
- WeChat PC 3.9.x integration via `wxauto` with polling loop and reconnect backoff.
- Message normalization for private/group chats, @-mention detection, and optional sender prefixing in group context.
- Text-only handling; non-text messages are ignored based on message type markers.
- In-memory conversation history per chat with max rounds, TTL, and total chat cap.
- Multi-preset API probing/selection with placeholder key detection and optional empty-key allowance.
- Hot-reload of `config.py` (and optional `ai_client.py`) with runtime settings updates.
- Emoji sanitization policies and configurable reply suffix templates.
- Safety throttles: random human-like delay and minimum reply interval.
- Filters: ignore official/service accounts, named chats, keywords, mute-filtered chats, and optional whitelist-only groups.
- **User profile management**: nickname, relationship, personality, and context facts storage.
- **Emotion detection**: keyword-based and AI-based emotion analysis with configurable modes.
- **Humanization**: time-aware prompts, conversation style adaptation, emotion trend analysis, and relationship evolution.
- **Personalized prompt generation**: analyze exported chat history to generate per-contact system prompts that mimic user's conversation style.

## Performance Optimizations
- `@dataclass(slots=True)` on `EmotionResult` for reduced memory footprint.
- `@lru_cache(maxsize=1024)` on token estimation to avoid redundant computation.
- `frozenset` for O(1) membership checks (emotion keywords, message type markers, allowed roles).
- Context manager support in `MemoryManager` for automatic resource cleanup.

## Data Workflow
1. **Export chat history**: Use [WeChatMsg](https://github.com/LC044/WeChatMsg) or the built-in CLI (`python -m tools.chat_exporter.cli`) to export WeChat chats to CSV format.
2. **Organize files**: Place exports in `chat_exports/聊天记录/<ContactName(wxid)>/<ContactName>.csv`.
3. **Generate prompts**: Run `python -m tools.prompt_gen.generator` to analyze chats and generate personalized prompts.
4. **Review output**: Check `chat_exports/top10_prompts_summary.json` for generated prompts.
5. **Integrate**: Copy prompts to `config.py`'s `system_prompt_overrides` or use `prompt_overrides.py`.

## Coding Style & Naming Conventions
- Python, 4-space indentation; keep type hints and docstrings consistent with existing modules.
- Naming: `snake_case` for functions/variables, `CapWords` for classes, `UPPER_SNAKE_CASE` for constants.
- No formatter or linter config is present; keep changes small and readable.

## Testing Guidelines
- Unit tests live in `tests/` and use the stdlib `unittest` runner.
- Run tests with `python -m unittest discover -s tests`.

## Commit & Pull Request Guidelines
- This checkout has no `.git` history, so no established commit message convention is available.
- Use short, imperative subjects (for example, "Add retry backoff") and explain config changes in the body.
- PRs should include: summary, linked issue if any, how you validated changes, and any config or logging impacts.

## Security & Configuration Tips
- `config.py` contains API keys; keep placeholders in version control and avoid sharing real secrets.
- Logs in `wxauto_logs/` may include message content; treat them as sensitive and do not commit them.
- `chat_exports/` contains sensitive chat history; keep it gitignored and do not share.


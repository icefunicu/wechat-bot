# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: entry point; connects to WeChat via `wxauto`, polls messages, filters/normalizes events, and sends replies. Handles config hot-reload, optional `ai_client.py` reload, reconnect backoff, and emoji sanitization.
- `ai_client.py`: OpenAI-compatible `/chat/completions` client using `httpx` (async); keeps per-chat in-memory history with TTL/size caps and retry backoff.
- `memory.py`: SQLite-backed chat history and user profile storage (nickname, relationship, personality, facts, emotion history).
- `emotion.py`: Emotion detection module supporting keyword and AI modes; time-awareness, conversation style analysis, and relationship evolution.
- `config.py`: runtime configuration (`CONFIG`/`get_config()`/`config`) for API presets, bot behavior, and logging.
- `requirements.txt`: runtime dependencies (includes `wxauto` from GitHub).
- `wxauto_logs/`: runtime logs (generated, rotating).
- `tests/`: unit tests for helper logic (no WeChat/API calls).
- `__pycache__/`, `.venv/`, `.idea/`: local artifacts; keep out of commits.

## Build, Test, and Development Commands
- `pip install -r requirements.txt`: install dependencies.
- `python main.py`: run the bot after editing `config.py`.
- `python -m unittest discover -s tests`: run unit tests.
- The app targets Windows + WeChat PC 3.9.x (4.x not supported). Keep the client logged in and running.
- `config.py` changes are polled and hot-reloaded; `main.py` changes require a restart.

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

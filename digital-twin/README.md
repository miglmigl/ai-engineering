# Digital Twin

An AI chatbot for my personal portfolio that answers visitor questions about my career, background, and skills - speaking as me. Built on OpenAI's API with function/tool calling: when a visitor wants to get in touch or asks something the twin can't answer, it logs the event to a local database and sends me a Telegram notification.

Originally built from Ed Donner's "AI Engineer" course (Week 1, Lab 4), then extended with production-style practices — persistent storage and Telegram notifications in place of the course's no-persistence, Pushover-based version.

## Current status

MVP skeleton, runnable as notebook cells. Not yet containerized, deployed, or split into modules — that's planned for later phases.

## Tech stack

- Python, OpenAI API (chat + tool calling)
- Gradio for the chat UI
- SQLAlchemy + SQLite for local persistence (leads and unanswered questions)
- Telegram Bot API for notifications
- `uv` for dependency management

## Setup

1. Install dependencies:
   ```
   uv sync
   ```
2. Copy `.env.example` to `.env` and fill in real values:
   - `OPENAI_API_KEY` — OpenAI API key
   - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — create a bot via [@BotFather](https://t.me/BotFather), get your chat ID via [@userinfobot](https://t.me/userinfobot)
3. Add knowledge source files to `twin/` (not tracked in git):
   - `twin/linkedin.pdf` — LinkedIn profile export
   - `twin/summary.txt` — curated career summary
4. Open `digital_twin_notebook.ipynb` and run the cells top to bottom.
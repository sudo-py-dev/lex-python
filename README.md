![Lex Banner](assets/lex_bot_banner.png)

# 🌐 lex-tg: The Ultimate Telegram Guardian

[English](#) | [עברית](README.he.md)

**lex-tg** is a state-of-the-art, modular Telegram group management system built for high-performance and absolute reliability. Leveraging the **MTProto** protocol and a modern asynchronous stack, lex-tg provides unparalleled control over group dynamics with a focus on speed, localization, and robust type safety.

---

## ✨ Core Features

- 🛡️ **Advanced Moderation**: Granular control over bans, kicks, and mutes with customizable expiry.
- 🔒 **Dynamic Locks**: Lock down text, media, stickers, URLs, or even bot commands instantly.
- ⚡ **AI Assistant**: Native integration with Google Gemini and OpenAI for intelligent group assistance and automated responses.
- 🌊 **Flood & Raid Control**: Intelligent rate-limiting and lockdown mechanisms to prevent group spam and malicious raids.
- 🌍 **Deep Localization**: Full multi-lingual support powered by a smart, centralized translation engine (20+ languages).
- 🎛️ **Premium Admin Panel**: Intuitive, callback-driven UI for effortless group configuration.
- 🧩 **Flattened Architecture**: Highly optimized, single-file plugin system for maximum maintainability.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Core Client** | [Pyrogram](https://docs.pyrogram.org/) (Async MTProto) |
| **Database** | [PostgreSQL](https://www.postgresql.org/) (via [asyncpg](https://github.com/MagicStack/asyncpg)) |
| **Migrations** | [Alembic](https://alembic.sqlalchemy.org/) (Asynchronous automation) |
| **Package Manager** | [uv](https://astral.sh/uv/) (Extreme performance & isolation) |
| **Type Safety** | [Mypy](https://mypy-lang.org/) (Strict null-safety & guard patterns) |

---

## 🚀 Quick Start

### 1. Install `uv`
Lex requires `uv` for lightning-fast dependency resolution and isolated environments.
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Setup Environment
Clone the repository and sync the dependencies:
```bash
uv sync
cp .env.example .env
```
> [!IMPORTANT]
> Ensure you fill in your `API_ID`, `API_HASH`, and `BOT_TOKEN` in the `.env` file. You can also customize the `BOT_NAME` in `src/config.py` (default: `lex-tg`).

### 3. Run the Bot
```bash
uv run bot
```

---

## 🛳️ Deployment (Running 24/7)

### Option 1: Railway (Recommended)
The easiest way to deploy Lex.
1. Click **New Project** on Railway.
2. Select your repository.
3. Add a **PostgreSQL** database.
4. Follow the [RAILWAY_GUIDE.md](RAILWAY_GUIDE.md) for environment variables and volumes.

### Option 2: Docker (Self-Hosted)
Ensure you have Docker and Docker Compose installed on your VPS.

1. **Setup**:
   ```bash
   bash scripts/deploy_vps.sh
   ```
2. **Manage**:
   - View logs: `docker compose logs -f`
   - Stop bot: `docker compose down`
   - Start bot: `docker compose up -d`

### Option 2: Systemd (Native Linux Service)
If you prefer running without Docker:

1. Copy the service file:
   ```bash
   sudo cp lex-tg.service /etc/systemd/system/
   ```
2. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable lex-tg
   sudo systemctl start lex-tg
   ```
3. View logs: `journalctl -u lex-tg -f`

---

## 🏗️ Development & Quality Assurance

We maintain rigorous standards for code quality and reliability.

### 🔍 Static Analysis
```bash
uv run lint         # Ultra-fast linting with Ruff
uv run fmt          # Automatic code formatting
uv run typecheck    # Strict type-checking with MyPy
```

### 🌐 Localization Workflow
Our smart translation tool ensures all languages stay in sync:
```bash
uv run translate    # Sync all locales from en.json
```

### 🧪 Automated Testing
```bash
uv run test         # Comprehensive pytest-asyncio suite
```

### 🗄️ Database Migrations
Always ensure your database schema is up-to-date:
```bash
uv run migrate      # Upgrade to the latest schema (alembic)
```

---

## 🏛️ Project Architecture

```text
├── src/
│   ├── core/           # Bot initialization and core client
│   ├── plugins/        # Flattened modular feature sets
│   │   ├── admin_panel/ # UI-driven configuration engine
│   │   ├── ai_assistant/ # LLM integration layer
│   │   ├── scheduler/   # Background task management
│   │   └── ...         # 30+ flattened plugin files
│   ├── repository/     # Data access layer (SQLAlchemy Models)
│   ├── locales/        # Internationalization schemas (.json)
│   └── utils/          # Hardened helpers (Permissions, Cache, i18n)
├── scripts/            # DevOps and localization automation
└── tests/              # Comprehensive test suites
```

---

## 💎 Project Status: High-Performance Hardening
Lex has been fully migrated to a **pure Python caching layer**, removing standard external dependencies like Redis to minimize latency and simplify deployment. We maintain **100% type-coverage** for all core modules.

> [!NOTE]
> Contributions are welcome! Please ensure all pull requests pass `uv run lint` and `uv run typecheck` before submission.

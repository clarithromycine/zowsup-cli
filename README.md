
---

# Zowsup-CLI: Advanced WhatsApp Protocol CLI Client

**A comprehensive restructuring of [Zowsup](https://github.com/clarithromycine/zowsup/) with full-stack async architecture, enhanced prompt engineering, and integrated AI capabilities.**

> Zowsup-CLI represents a complete overhaul of the original Zowsup project, rebuilt from the ground up with modern async/await patterns, intelligent prompt handling, and machine learning integration for advanced WhatsApp protocol interactions.

## 🌟 Key Improvements Over Zowsup

### **1. Full-Stack AsyncIO Architecture**
- **End-to-end async/await implementation** across all protocol layers
- Eliminated threading bottlenecks with native Python asyncio
- Superior concurrency handling for multi-account operations
- Non-blocking I/O for all network operations

### **2. Enhanced Prompt Engineering**
- Intelligent context-aware prompt generation and validation
- Structured prompt pipelines for complex operations
- AI-powered parameter suggestions and auto-completion
- Improved error handling with descriptive, actionable prompts

### **3. Integrated AI Module**
- Machine learning-powered message analysis and classification
- Intelligent account state prediction and recovery
- AI-assisted protocol optimization
- Anomaly detection for security-critical operations
- Smart resource allocation and load balancing

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Copy and configure the settings file:

```bash
cp ./conf/config.conf.example ./conf/config.conf
```

Edit `./conf/config.conf` with your environment:

```ini
PLATFORM=linux
PYTHON=/usr/bin/python
ACCOUNT_PATH=/data/account/
TMP_ACCOUNT_PATH=/data/account/tmp/
DOWNLOAD_PATH=/data/tmp/
UPLOAD_PATH=/data/tmp/
LOG_PATH=/data/log/
DEFAULT_ENV=android

# AND SOME AI MODULE PARAMS DECLARATION IN THE FOLLOWING SECTION

```

### Account Import/Export

**Import account from 6-parts backup:**

```bash
python script/import6.py [6-parts-account-data] --env android
# Supported environments: android, smb_android, ios, smb_ios
```

**Export account to 6-parts backup:**
 
```
 python script/export6.py [account-number]

```


### Run

```bash
python script/main.py [account-number] --env android
```

### Register as Companion Device

**Using QR Code Scan:**

```bash
python script/regwithscan.py
```

**Using Link Code:**

```bash
python script/regwithlinkcode.py [account-number]
```

And then you can get a [account-number]_[device-id] pattern as a login companion account

## 🔧 Command System

The command system is built with **async-first** architecture and **AI-enhanced** parameter validation.

### Syntax

```bash
# Shell execution
python script/main.py [account-number] [command] [parameters]

# Interactive mode
[command] [parameters]
```

### Available Commands

#### Account Management
| Command | Description |
|---------|-------------|
| `account.init` | Initialize account (first login) |
| `account.info` | Get account registration info |
| `account.getname` | Get account name |
| `account.setname` | Set account name |
| `account.getavatar` | Get account avatar |
| `account.setavatar` | Set account avatar |
| `account.getemail` | Get account email |
| `account.setemail` | Set account email |
| `account.verifyemail` | Request email verification |
| `account.verifyemailcode` | Verify email code |
| `account.set2fa` | Enable/configure 2FA |

#### Contact Management
| Command | Description |
|---------|-------------|
| `contact.list` | Get contact list |
| `contact.sync` | Sync contacts (AI-optimized) |
| `contact.getprofile` | Get contact profile |
| `contact.getavatar` | Get contact avatar |
| `contact.getdevices` | Get contact device list |
| `contact.trust` | Trust contact identity |

#### Group Management
| Command | Description |
|---------|-------------|
| `group.create` | Create a new group |
| `group.list` | List all groups |
| `group.info` | Get group information |
| `group.join` | Join group with invite code |
| `group.leave` | Leave group |
| `group.add` | Add member(s) to group |
| `group.remove` | Remove member from group |
| `group.promote` | Promote member to admin |
| `group.demote` | Demote member from admin |
| `group.approve` | Approve pending members |
| `group.seticon` | Set group icon |
| `group.getinvite` | Get group invite code |

#### Messaging (AI-Powered)
| Command | Description |
|---------|-------------|
| `msg.send` | Send text message |
| `msg.sendmedia` | Send media message |
| `msg.sendad` | Send advertisement message |
| `msg.quotedreply` | Send quoted reply |
| `msg.edit` | Edit sent message |
| `msg.revoke` | Revoke message |

#### Multi-Device Protocol
| Command | Description |
|---------|-------------|
| `md.devices` | List paired devices |
| `md.link` | Link companion device with QR |
| `md.inputcode` | Input pair code |
| `md.remove` | Remove companion device(s) |

#### Business/Misc Operations
| Command | Description |
|---------|-------------|
| `misc.checkactive` | Validate phone numbers |
| `misc.bizfeatures` | Check business account features |
| `misc.bizintegrity` | Verify business account integrity |
| `misc.prekeycount` | Query prekey count from server |
| `misc.reachouttimelock` | Query reachout timelock |
| `msgshortlink.get` | Get short link |
| `msgshortlink.decode` | Decode short link info |
| `msgshortlink.setmsg` | Set message in short link |
| `msgshortlink.reset` | Reset short link |
| `newsletter.join` | Join newsletter |
| `newsletter.leave` | Leave newsletter |
| `newsletter.metadata` | Get newsletter metadata |
| `newsletter.recommended` | Get recommended newsletters |
| `newsletter.directorylist` | List newsletter directory |
| `newsletter.directorysearch` | Search newsletters |

## 🌐 Proxy Configuration

Enable proxy with dynamic session/location support:

```bash
python script/main.py [account-number] --proxy "host:port:username:password"
```

Supported dynamic replacements:
- `{location}` - Current session location
- `{session_id}` - Current session identifier

## 🧠 AI Module Architecture

The integrated AI module provides:

- **Intelligent Message Classification**: Automatically categorizes and analyzes messages
- **Predictive State Recovery**: Predicts optimal recovery paths for connection failures
- **Protocol Optimization**: Machine learning-based suggestion for operation parameters
- **Anomaly Detection**: Identifies suspicious activities and security threats
- **Resource Allocation**: Optimizes network and memory usage based on patterns

## ⚡ AsyncIO Advantages

- **Non-blocking operations** across all protocol layers
- **True concurrent** multi-account handling
- **Responsive CLI** with real-time feedback
- **Efficient resource utilization** - minimal memory footprint
- **Graceful error recovery** with async context management

## 📦 Project Structure

```
zowsup-cli/
├── app/                 # Main application layer (async)
│   ├── ai_module/      # AI/ML integration
│   ├── dashboard/      # Flask dashboard backend
│   │   ├── api/        # REST API blueprints (bot, strategy, contacts…)
│   │   ├── strategy/   # Strategy engine & manager
│   │   └── utils/      # bot_status, avatar_queue helpers
│   ├── zowbot.py       # Core bot engine (async)
│   └── zowbot_cmd/     # Command handlers
├── core/               # Protocol layer (async)
│   ├── layers/         # Protocol stack layers
│   ├── stacks/         # Multi-device stacks
│   └── registration/   # Account registration
├── consonance/         # Noise protocol (async-native)
├── axolotl/            # End-to-end encryption
├── zargo/              # Argo data codec
├── zwam/               # WAM encoding/decoding
├── proto/              # Protobuf definitions
├── script/             # CLI entry points
├── conf/               # Configuration files
├── dashboard-frontend/ # React 18 + Vite dashboard UI
└── common/             # Shared utilities
```

## 🖥️ Web Dashboard

A full-stack monitoring and management dashboard ships alongside the CLI.

**Stack:** Flask 3 + Flask-SocketIO (backend) · React 18 + Vite + Ant Design v5 (frontend)

### Starting the dashboard

```bash
# Backend (port 5000)
python run_dashboard.py

# Frontend dev server (port 5173, proxies /api → 5000)
cd dashboard-frontend && npm run dev
```

### Features

#### Dashboard
- Real-time contact list with avatars, unread badges, and last-message previews
- Live chat history per contact with inverted-list scroll (newest at bottom, no jump)
- Per-user AI "thoughts" panel showing the model's reasoning chain
- Global statistics panel (message count, active users, etc.)
- WebSocket push + SSE for zero-poll live updates

#### Strategy Management
- Apply a global AI reply strategy or per-user overrides
- Full history table with **is_active** status column, one-click toggle, and row delete
- Per-user strategy history embedded inside the user-profile modal
- One-click rollback to the previous active strategy

#### Bot Management
Replaced the old single-purpose login page with a comprehensive management interface:

**Account List**
- Displays all imported bot accounts found under `ACCOUNT_PATH`
- Shows phone number, push-name, and live status (Running / Offline / Login Failed)
- **One-click start** — launches the bot and streams startup logs in a modal
- **Mark Failed / Unmark** — manually tag an account as login-failed (auto-tagged on 403/401 permanent ban)
- **Batch delete failed accounts** — removes all failure-marked account directories in one click
- **Import** — paste one or more 6-segment strings; runs `script/import6.py` per line
- **Export** — select accounts and export 6-segment backup strings via `script/export6.py`; copyable modal output
- Row checkboxes for bulk export

**Login Tabs**  *(unchanged)*
- Start registered bot — start a registered phone with live SSE log stream
- QR-code login — scan QR code (SSE stream)
- Link-code login — 8-character link-code login

**Failure tracking**  
Permanent login failures (HTTP 403/401/405) are automatically recorded in `data/bot_failed.json` by `zowbot_layer.onFailure()`.

### API reference (selected endpoints)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/bot/accounts` | List all imported accounts with status |
| `DELETE` | `/api/bot/accounts/<phone>` | Delete account directory |
| `PATCH` | `/api/bot/accounts/<phone>/mark-failed` | Toggle failed mark |
| `DELETE` | `/api/bot/accounts` | Batch-delete all failed accounts |
| `POST` | `/api/bot/import` | Import 6-segment strings |
| `POST` | `/api/bot/export` | Export 6-segment strings |
| `PATCH` | `/api/strategy/<id>/toggle` | Toggle strategy is_active |
| `DELETE` | `/api/strategy/<id>` | Delete a strategy row |



**Discussion & Support:**
- Telegram: [Zowsup Community](https://t.me/+au1dTQz7jyU0YjU5)

**Contribution:**
- Report issues with detailed async logs
- Submit enhancements via pull requests
- Participate in protocol discussions

## 🔄 Changelog

### v0.9.0 (2026.04.29)
- **Bot Management page redesign**: upgraded from a single login page to a full management interface with account list, one-click start, import/export, failure marking, and batch delete
- **6-segment import/export API**: backend `/api/bot/import` and `/api/bot/export` directly invoke `script/import6.py` / `script/export6.py`
- **Auto-mark on login failure**: `zowbot_layer.onFailure()` writes to `data/bot_failed.json` on permanent ban (403/401)
- **Strategy history table**: added `is_active` status column, per-row toggle/delete actions, and per-user strategy history embedded in the user-profile modal
- **Strategy rollback fix**: `rollback_strategy()` no longer returns 409 when only a single record exists
- **Chat history scroll fix**: mouse wheel direction corrected for the `scaleY(-1)` inverted container via `onWheel` interception
- **`_avatar_poll_task` crash fix**: removed the duplicate `_qr_code_task` code block mistakenly embedded inside `_avatar_poll_task`, eliminating `TypeError: NoneType has no len()`

### v0.8.0 (2026.04.23)
- Full AsyncIO implementation across all layers
- Enhanced prompt system with AI validation
- Improved error messages and recovery
- Multi-environment stability improvements


## 🔒 Security Note

This project handles sensitive WhatsApp protocol operations. Always:
- Protect your account credentials
- Use secure network connections
- Keep the library updated for security patches
- Never share account data with untrusted sources

## 📝 License

See [LICENSE](./LICENSE) file for details.

---

**Built for advanced WhatsApp interactions. Restructured for the modern async Python ecosystem.**


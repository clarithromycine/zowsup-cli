
---

# Zowsup-CLI: Advanced WhatsApp Protocol Client

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

## 📦 Core Project Structure

```
zowsup-cli/
├── app/                 # Main application layer (async)
│   ├── ai_module/      # AI/ML integration
│   ├── zowbot.py       # Core bot engine (async)
│   └── zowbot_cmd/     # Command handlers
├── core/               # Protocol layer (async)
│   ├── layers/         # Protocol stack layers
│   ├── stacks/         # Multi-device stacks
│   └── registration/   # Account registration
├── proto/              # Protobuf definitions
├── script/             # CLI entry points
├── conf/               # Configuration files
└── common/             # Shared utilities
```

## 💬 Community & Support

**Discussion & Support:**
- Telegram: [Zowsup Community](https://t.me/+au1dTQz7jyU0YjU5)

**Contribution:**
- Report issues with detailed async logs
- Submit enhancements via pull requests
- Participate in protocol discussions

## 🔄 Changelog

### v0.8.0 (Latest release at 2026.04.23)
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


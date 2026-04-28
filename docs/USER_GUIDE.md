# Zowsup Dashboard — User Guide

## Overview

The Zowsup Dashboard provides a real-time view of WhatsApp conversation
data processed by the Zowsup bot.  It shows:

- **Contact list** — all tracked WhatsApp contacts
- **Chat history** — paginated message log per contact
- **User portrait** — AI-computed profile (language, sentiment, topics)
- **Strategy management** — apply and track AI response strategies
- **Statistics** — daily message counts and activity trends

---

## Accessing the dashboard

1. Open your browser and navigate to the dashboard URL (e.g., http://localhost or your server's IP).
2. If authentication is configured, enter the API token when prompted
   (or set it as a URL parameter: `?token=<your-token>`).

---

## Main layout

```
┌────────────────────────────────────────────────────────────┐
│  Navigation bar                               [⚙ Settings] │
├──────────────┬─────────────────────┬──────────────────────┤
│ Contact list │   Chat history      │  User portrait       │
│              │                     │                      │
│ 🔍 Search   │  [← prev] [next →]  │  Sentiment: 0.72     │
│             │                     │  Topics: travel, food │
│  Alice      │  Alice: "hi"        │  Risk: low           │
│  Bob        │  Bot: "Hello!"      │                      │
│  ...        │  ...                │  [Apply Strategy]    │
└──────────────┴─────────────────────┴──────────────────────┘
│ Statistics: 1,234 messages | 45 active users | ...         │
└────────────────────────────────────────────────────────────┘
```

---

## Features

### Contact list (left panel)

- Lists all contacts the bot has interacted with.
- Use the **search box** to filter by name or phone number.
- Click a contact to load their chat history and portrait.

### Chat history (centre panel)

- Displays messages in reverse-chronological order (newest first).
- Use **Previous / Next** buttons to paginate (20 messages per page).
- Messages sent by the bot are shown with a different background colour.

### User portrait (right panel)

Shows the AI-computed portrait for the selected contact:

| Field | Description |
|-------|-------------|
| Display name | WhatsApp display name |
| Language | Detected primary language |
| Sentiment | Score from -1 (negative) to +1 (positive) |
| Topics | Top conversation topics |
| Risk level | `low` / `medium` / `high` |
| Last active | Timestamp of most recent message |

### Strategy management

1. Click **Apply Strategy** in the user portrait panel.
2. Choose a strategy from the dropdown.
3. Optionally adjust strategy parameters.
4. Click **Apply** — the strategy is saved and the bot will use it for future replies.

To apply a strategy to **all contacts** at once, use the **Global Strategy** button in the navigation bar.

#### Strategy history

View past applications under the **Strategy** → **History** tab.
Use **Rollback** to revert a strategy to the previous one.

### Statistics page

Navigate to **Statistics** in the nav bar to see:

- Total messages and users
- Daily message volume chart (last 7 days by default; adjust with the date range picker)
- Active users over time

---

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `←` / `→` | Previous / next page in chat history |
| `Ctrl+K` | Focus the contact search box |
| `Esc` | Close any open modal |

---

## API access

All data is available via the REST API.
Browse the interactive API documentation at:

```
http://localhost:5000/api/docs
```

Include the Bearer token in your requests:

```bash
curl -H "Authorization: Bearer <token>" http://localhost:5000/api/statistics
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Page shows "Loading…" indefinitely | Check that the backend is running at port 5000 |
| "Unauthorized" error | Check the API token in Settings |
| Contact list is empty | The bot hasn't processed any messages yet |
| Charts don't update | Refresh the page; real-time updates via WebSocket require an active connection |

"""One-shot script: fix UTF-8 mojibake in group display_names already stored in DB."""
import sqlite3

DB = "data/dashboard.db"
conn = sqlite3.connect(DB)

rows = conn.execute(
    "SELECT user_jid, display_name FROM user_profiles"
    " WHERE user_jid LIKE '%@g.us' AND display_name IS NOT NULL"
).fetchall()

fixed = 0
for jid, name in rows:
    try:
        corrected = name.encode("latin-1").decode("utf-8")
        if corrected != name:
            conn.execute(
                "UPDATE user_profiles SET display_name=? WHERE user_jid=?",
                (corrected, jid),
            )
            print(f"Fixed: {jid}  {name!r} -> {corrected!r}")
            fixed += 1
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass  # already valid Unicode, skip

conn.commit()
conn.close()
print(f"Done. {fixed} group name(s) corrected.")

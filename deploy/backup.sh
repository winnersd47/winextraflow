#!/usr/bin/env bash
# WinExtraFlow — nightly backup of the DB and the Telethon session.
# The session file is as important as the DB: losing it means re-authorising
# the Telegram account by phone code.
set -euo pipefail

BACKEND=/opt/winextraflow/backend
DEST=/var/backups/winextraflow
KEEP_DAYS=14
STAMP=$(date +%Y%m%d-%H%M)

mkdir -p "$DEST"

# SQLite: use the online backup API so we never copy a half-written file.
if [ -f "$BACKEND/winextraflow.db" ]; then
    sqlite3 "$BACKEND/winextraflow.db" ".backup '$DEST/db-$STAMP.sqlite'"
    gzip -f "$DEST/db-$STAMP.sqlite"
    echo "$(date -Is) db backed up -> db-$STAMP.sqlite.gz"
fi

# Telethon session(s)
for s in "$BACKEND"/*.session; do
    [ -e "$s" ] || continue
    cp "$s" "$DEST/$(basename "$s" .session)-$STAMP.session"
done

# Config (contains secrets — keep the backup dir root-only: chmod 700)
[ -f "$BACKEND/.env" ] && cp "$BACKEND/.env" "$DEST/env-$STAMP"

# Retention
find "$DEST" -type f -mtime +$KEEP_DAYS -delete
echo "$(date -Is) backup done, pruned older than ${KEEP_DAYS}d"

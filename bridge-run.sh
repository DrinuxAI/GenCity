#!/bin/bash
export PATH="/opt/homebrew/bin:/Users/marcomasciadri/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "/Users/marcomasciadri/Documents/Gen Agents Office" || exit 1
pgrep -f "python3 bridge.py" >/dev/null && { echo "$(date '+%F %T') bridge già in esecuzione"; exit 0; }
python3 bridge.py --full || { echo "$(date '+%F %T') bridge fallito"; exit 1; }
if ! git diff --quiet -- data.json; then
  git add data.json
  git commit -m "data: snapshot GenTeam $(date '+%F %H:%M')" >/dev/null
  if git push -q origin main; then
    echo "$(date '+%F %T') push ok: $(git log -1 --format=%h)"
  else
    echo "$(date '+%F %T') push fallito"
  fi
else
  echo "$(date '+%F %T') nessun cambiamento"
fi

#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "/Users/marcomasciadri/GenCity" || exit 1
M=$(date +%Y-%m)
python3 archive.py --inc >> /Users/marcomasciadri/Library/Logs/gencity-weekly.log 2>&1
python3 archive.py --export --month $M >> /Users/marcomasciadri/Library/Logs/gencity-weekly.log 2>&1
python3 archive.py --md --month $M >> /Users/marcomasciadri/Library/Logs/gencity-weekly.log 2>&1
echo "$(date '+%F %T') weekly ok ($M)" >> /Users/marcomasciadri/Library/Logs/gencity-weekly.log

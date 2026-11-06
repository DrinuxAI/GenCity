#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "/Users/marcomasciadri/GenCity" || exit 1
python3 report_email.py

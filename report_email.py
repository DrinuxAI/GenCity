#!/usr/bin/env python3
import json
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo("Europe/Zurich")
TO = "marco@masciadri.net"
SITE = "https://gencity.masciadri.net"
ST_LABEL = {"working": "Al lavoro", "attention": "Attenzione", "idle": "In pausa"}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def trunc(s, n):
    s = (s or "").strip().replace("\n", " ")
    return s[: n - 1] + "…" if len(s) > n else s


def chat_url(c):
    return "https://www.genspark.ai/genteam/genspark/channel/" + c["id"]


def main():
    with open(os.path.join(HERE, "data.json"), encoding="utf-8") as f:
        d = json.load(f)
    chats = d.get("chats", [])
    waiting = [c for c in chats if c.get("needs_marco")]
    now = datetime.now(TZ)

    td = "font:14px/1.5 -apple-system,Helvetica,Arial,sans-serif;color:#1c2340;"
    h = '<div style="' + td + 'max-width:720px">'
    h += '<h1 style="font-size:19px;margin:0 0 4px">GenCity — Report attività</h1>'
    h += '<p style="color:#6b7299;font-size:12px;margin:0 0 18px">Generato ' + now.strftime("%d/%m/%Y alle %H:%M") + " · " + str(len(chats)) + ' chat monitorate · <a href="' + SITE + '" style="color:#2563eb">apri la città</a></p>'

    if waiting:
        h += '<h2 style="font-size:15px;color:#b91c1c;margin:18px 0 8px">⚠️ Attende una tua risposta (' + str(len(waiting)) + ')</h2>'
        for c in waiting:
            last = c["messages"][-1] if c.get("messages") else None
            h += '<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:10px 14px;margin:8px 0">'
            h += '<b>' + esc(c["name"]) + '</b> — ' + str(c.get("unread") or 0) + ' messaggi non letti'
            if last:
                h += '<br><span style="color:#555">' + esc(trunc(last.get("text"), 160)) + '</span>'
            h += ' <a href="' + chat_url(c) + '" style="color:#2563eb;font-size:12px">Apri in GenTeam ↗</a></div>'
    else:
        h += '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:10px 14px;margin:0 0 16px;color:#166534">✓ Nessuna chat attende una tua risposta.</div>'

    h += '<h2 style="font-size:15px;margin:20px 0 8px">Agenti — panoramica</h2>'
    h += '<table style="width:100%;border-collapse:collapse;font-size:13px">'
    for c in chats:
        for a in c.get("agents", []):
            if a.get("name") == "Tu":
                continue
            color = {"working": "#b45309", "attention": "#b91c1c", "idle": "#6b7299"}.get(a.get("status"), "#6b7299")
            h += '<tr style="border-bottom:1px solid #eef0f6">'
            h += '<td style="padding:5px 8px 5px 0;white-space:nowrap"><b>' + esc(a.get("name")) + '</b><br><span style="color:#6b7299;font-size:11px">' + esc(c["name"]) + '</span></td>'
            h += '<td style="padding:5px 8px"><span style="color:' + color + ';font-weight:600;font-size:12px">' + ST_LABEL.get(a.get("status"), a.get("status")) + '</span></td>'
            h += '<td style="padding:5px 0">' + esc(trunc(a.get("task"), 110)) + '</td></tr>'
    h += '</table>'

    names = {}
    for c in chats:
        for a in c.get("agents", []):
            names[str(a.get("id", "")).split("@")[0]] = a.get("name")
    cross = {}
    for c in chats:
        for m in c.get("messages", []):
            f = str(m.get("from", ""))
            if f.startswith("agent_"):
                cross.setdefault(f.split("@")[0], set()).add(c["name"])
    multi = sorted(
        ((names.get(b, b), s) for b, s in cross.items() if len(s) > 1),
        key=lambda x: -len(x[1]),
    )
    if multi:
        h += '<h2 style="font-size:15px;margin:20px 0 8px">🔁 Attività incrociata tra chat</h2>'
        for nm, s in multi[:12]:
            h += '<div style="font-size:13px;padding:5px 0;border-bottom:1px solid #eef0f6"><b>' + esc(nm) + '</b> attivo in: ' + esc(", ".join(sorted(s))) + '</div>'
    else:
        h += '<h2 style="font-size:15px;margin:20px 0 8px">🔁 Attività incrociata tra chat</h2>'
        h += '<div style="font-size:13px;color:#6b7299">Nessun agente attivo in più chat negli ultimi messaggi raccolti.</div>'

    h += '<h2 style="font-size:15px;margin:20px 0 8px">Chat — ultimo messaggio</h2>'
    for c in chats:
        last = c["messages"][-1] if c.get("messages") else None
        h += '<div style="border-bottom:1px solid #eef0f6;padding:7px 0;font-size:13px">'
        h += '<b>' + esc(c["name"]) + '</b>' + (' <span style="color:#b91c1c;font-size:11px;font-weight:600">⚠ attende te</span>' if c.get("needs_marco") else '')
        if last:
            who = "Tu" if str(last.get("from", "")).startswith("human") else esc((last.get("from") or "").split("@")[0])
            h += '<br><span style="color:#555"><span style="color:#6b7299;font-size:11px">' + esc(last.get("time") or "") + '</span> ' + who + ': ' + esc(trunc(last.get("text"), 140)) + '</span>'
        h += ' <a href="' + chat_url(c) + '" style="color:#2563eb;font-size:12px">Apri ↗</a></div>'

    h += '<p style="color:#9aa0b8;font-size:11px;margin-top:20px">Email automatica di GenCity · bridge GenTeam · ogni mattina alle 08:00 · dati aggiornati ' + esc((d.get("generated_at") or "")[:16].replace("T", " ")) + ' UTC</p></div>'

    n_wait = len(waiting)
    subject = "GenCity — ⚠️ " + str(n_wait) + " chat attendono risposta" if n_wait else "GenCity — tutto in ordine, nessuna attesa"
    args = {"to": TO, "subject": subject, "body": h, "content_type": "text/html"}
    p = subprocess.run(
        ["gsk", "connector", "call", "gmail", "-t", "send", "-a", json.dumps(args), "--yes"],
        capture_output=True, text=True, timeout=180,
    )
    if '"status":"success"' in p.stdout:
        print("report inviato a", TO, "| attese:", n_wait)
    else:
        raise RuntimeError("invio fallito: " + (p.stderr[:300] or p.stdout[:300]))


if __name__ == "__main__":
    main()

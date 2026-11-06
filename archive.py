#!/usr/bin/env python3
import argparse
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, "archive.jsonl")
SERVER_SLUG = "genspark"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def gsk(*args, timeout=180):
    p = subprocess.run(["gsk", *args], capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "")[:300])
    return json.loads(p.stdout).get("data", {})


def load_ids():
    ids = set()
    if os.path.exists(ARCHIVE):
        with open(ARCHIVE, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    ids.add(r.get("id"))
                except Exception:
                    pass
    return ids


def do_search(q, chat, limit):
    ql = q.lower()
    hits = []
    if not os.path.exists(ARCHIVE):
        print("Archivio vuoto: esegui prima python3 archive.py")
        return
    with open(ARCHIVE, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if chat:
                cl = chat.lower()
                if cl not in (r.get("channel_name") or "").lower() and cl not in (r.get("channel") or "").lower():
                    continue
            if ql in (r.get("text") or "").lower():
                hits.append(r)
    hits.sort(key=lambda r: r.get("ts") or "")
    for r in hits[-limit:]:
        t = (r.get("ts") or "")[:16].replace("T", " ")
        who = r.get("sender_name") or r.get("sender_type") or "?"
        print(f"[{t}] {r.get('channel_name')} — {who}: {(r.get('text') or '')[:180]}")
    print(f"({len(hits)} risultati totali, ultimi {min(len(hits), limit)} mostrati)")


def paginate_read(out, cid, known, label, ch_type, is_thread=False, inc=False):
    new = 0
    seen = set()
    before = None
    while True:
        try:
            items = gsk("genteam", "read", "--channel_id", cid,
                        "--limit", "200", *(["--before_message_id", before] if before else [])).get("items", [])
        except Exception as e:
            print("  ERR", label, str(e)[:120])
            break
        msgs = [it for it in items if it.get("kind") == "message_recorded" and it.get("data", {}).get("comet_message_id")]
        if not msgs:
            break
        batch_new = 0
        for it in msgs:
            d = it["data"]
            mid = d["comet_message_id"]
            if mid in known or mid in seen:
                continue
            seen.add(mid)
            rec = {
                "id": mid,
                "channel": cid,
                "channel_name": label,
                "channel_type": ch_type,
                "thread": is_thread,
                "sender_id": d.get("sender_actor_id"),
                "sender_name": d.get("sender_display_name"),
                "sender_type": d.get("sender_actor_type"),
                "ts": it.get("ts") or d.get("sent_at"),
                "text": (d.get("content") or "").strip(),
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            known.add(mid)
            batch_new += 1
        new += batch_new
        if inc:
            break
        if batch_new == 0 and len(msgs) < 200:
            break
        before = msgs[-1]["data"]["comet_message_id"]
    return new


def do_export(month, out_pdf):
    if not os.path.exists(ARCHIVE):
        print("Archivio vuoto: esegui prima python3 archive.py")
        return
    recs = []
    with open(ARCHIVE, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            ts = r.get("ts") or ""
            if month and not ts.startswith(month):
                continue
            if (r.get("text") or "").strip():
                recs.append(r)
    if not recs:
        print(f"Nessun messaggio nel mese {month}")
        return
    recs.sort(key=lambda r: r.get("ts") or "")
    by_chat = {}
    for r in recs:
        by_chat.setdefault(r.get("channel_name") or "?", []).append(r)
    anno, mese = month.split("-")
    titolo = f"{MESI[int(mese) - 1]} {anno}"

    def day_hist(rows):
        from collections import Counter
        c = Counter((r.get("ts") or "")[8:10] for r in rows)
        mx = max(c.values()) or 1
        days = sorted(c)
        return "".join(
            f'<div class="d"><span class="b" style="height:{max(8, int(34 * c[d] / mx))}px"></span>'
            f'<span class="n">{int(d)}</span></div>' for d in days)

    def authors(rows):
        from collections import Counter
        c = Counter((r.get("sender_name") or r.get("sender_type") or "?") for r in rows)
        return ", ".join(f"{esc(k)} ({v})" for k, v in c.most_common(6))

    h = """<!doctype html><html lang="it"><head><meta charset="utf-8"><style>
    @page{margin:16mm 14mm}
    body{font:10.5px/1.5 -apple-system,Helvetica,sans-serif;color:#1c2340;margin:0}
    .cover{border-bottom:3px solid #1c2340;padding-bottom:14px;margin-bottom:18px}
    h1{font-size:21px;margin:0 0 3px}
    .meta{color:#6b7299;font-size:10px}
    .stats{display:flex;gap:26px;margin:12px 0 2px}
    .stats b{font-size:17px;display:block}
    .stats span{font-size:9px;color:#6b7299;text-transform:uppercase;letter-spacing:.5px}
    .chat{page-break-inside:auto;margin:16px 0 22px;border:1px solid #dfe3ee;border-radius:8px;overflow:hidden}
    .chead{background:#f2f4fa;padding:8px 12px;page-break-inside:avoid;page-break-after:avoid}
    .chead b{font-size:13.5px}
    .chead .cn{color:#6b7299;font-size:9.5px;margin-top:2px}
    .hist{display:flex;align-items:flex-end;gap:2px;height:44px;padding:4px 12px 0}
    .hist .d{display:flex;flex-direction:column;align-items:center;width:16px}
    .hist .b{background:#39d0c4;border-radius:2px;width:10px;display:block}
    .hist .n{font-size:7px;color:#6b7299;margin-top:1px}
    .au{padding:4px 12px 8px;font-size:9.5px;color:#4a5280}
    table.msg{width:100%;border-collapse:collapse}
    table.msg td{border-top:1px solid #eef1f7;padding:3px 12px;vertical-align:top;font-size:9.5px}
    td.t{color:#6b7299;white-space:nowrap;width:86px}
    td.w{width:110px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    td.x{word-break:break-word}
    .th{background:#1c2340;color:#fff;padding:6px 12px;font-weight:700;font-size:10.5px;page-break-before:always}
    </style></head><body>"""
    n_chat = len(by_chat)
    n_auth = len({(r.get("sender_id") or r.get("sender_name")) for r in recs})
    n_th = len({r["id"] for r in recs if r.get("thread")})
    h += f'<div class="cover"><h1>GenTeam — Report mensile · {esc(titolo)}</h1>'
    h += f'<div class="meta">Archivio locale GenCity · generato {__import__("datetime").datetime.now().strftime("%d/%m/%Y %H:%M")}</div>'
    h += f'<div class="stats"><div><b>{len(recs)}</b><span>messaggi</span></div><div><b>{n_chat}</b><span>chat</span></div><div><b>{n_auth}</b><span>partecipanti</span></div><div><b>{n_th}</b><span>in thread</span></div></div></div>'
    for name, rows in sorted(by_chat.items(), key=lambda kv: -len(kv[1])):
        h += f'<div class="chat"><div class="chead"><b>{esc(name)}</b><div class="cn">{len(rows)} messaggi · attività: {esc((rows[0].get("ts") or "")[8:10] + "/" + mese)} → {esc((rows[-1].get("ts") or "")[8:10] + "/" + mese)} · autori: {authors(rows)}</div></div>'
        h += f'<div class="hist">{day_hist(rows)}</div></div>'
    for name, rows in sorted(by_chat.items(), key=lambda kv: -len(kv[1])):
        h += f'<div class="th">Transcript · {esc(name)} ({len(rows)} messaggi)</div><table class="msg">'
        for r in rows:
            t = (r.get("ts") or "")[11:16]
            g = (r.get("ts") or "")[8:10] + "/" + mese
            who = r.get("sender_name") or r.get("sender_type") or "?"
            th = " 🧵" if r.get("thread") else ""
            h += f'<tr><td class="t">{esc(g)} {esc(t)}{th}</td><td class="w">{esc(who)}</td><td class="x">{esc(r.get("text"))}</td></tr>'
        h += "</table>"
    h += "</body></html>"

    rdir = os.path.join(HERE, "reports")
    os.makedirs(rdir, exist_ok=True)
    base = os.path.join(rdir, f"report-{month}")
    htmlp = base + ".html"
    pdfp = out_pdf if out_pdf else base + ".pdf"
    with open(htmlp, "w", encoding="utf-8") as f:
        f.write(h)
    if not os.path.exists(CHROME):
        print(f"Chrome non trovato: HTML pronto in {htmlp} (aprilo e stampa in PDF)")
        return
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                        f"--print-to-pdf={pdfp}", "--no-pdf-header-footer", htmlp],
                       capture_output=True, text=True, timeout=120)
    if os.path.exists(pdfp):
        print(f"PDF esportato: {pdfp} | {len(recs)} messaggi, {n_chat} chat")
    else:
        print("PDF non generato:", (r.stderr or "")[:200], f"— HTML disponibile: {htmlp}")


def sanitize(s):
    return "".join(c for c in (s or "?") if c not in '/\\:*?"<>|').strip() or "chat"


def do_md(month):
    if not os.path.exists(ARCHIVE):
        print("Archivio vuoto: esegui prima python3 archive.py")
        return
    recs = []
    with open(ARCHIVE, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if (r.get("ts") or "").startswith(month) and (r.get("text") or "").strip():
                recs.append(r)
    if not recs:
        print(f"Nessun messaggio nel mese {month}")
        return
    recs.sort(key=lambda r: r.get("ts") or "")
    by_chat = {}
    for r in recs:
        by_chat.setdefault(r.get("channel_name") or "?", []).append(r)
    anno, mese = month.split("-")
    outdir = os.path.join(HERE, "brain", month)
    os.makedirs(outdir, exist_ok=True)
    files = []
    for name, rows in sorted(by_chat.items(), key=lambda kv: -len(kv[1])):
        safe = sanitize(name)
        fm = (f"---\ntitle: \"{esc(name)} — {MESI[int(mese) - 1]} {anno}\"\n"
              f"type: transcript\nsource: GenTeam\nchat: \"{name}\"\n"
              f"period: {month}\nmessages: {len(rows)}\n"
              f"generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}\n"
              "tags: [genteam, transcript]\n---\n\n")
        body = fm
        cur_day = None
        for r in rows:
            ts = r.get("ts") or ""
            day = ts[8:10] + "/" + mese + "/" + anno
            if day != cur_day:
                body += f"\n## 📅 {day}\n\n"
                cur_day = day
            t = ts[11:16]
            who = esc(r.get("sender_name") or r.get("sender_type") or "?")
            th = " 🧵" if r.get("thread") else ""
            txt = esc(r.get("text")).replace("\n", "\n  ")
            body += f"- **{t} · {who}**{th} — {txt}\n"
        fp = os.path.join(outdir, safe + ".md")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(body)
        files.append((safe, len(rows)))
    idx = (f"---\ntitle: \"GenTeam — indice {MESI[int(mese) - 1]} {anno}\"\n"
           f"type: index\nperiod: {month}\n"
           f"generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}\n"
           "tags: [genteam, indice]\n---\n\n"
           f"# GenTeam — {MESI[int(mese) - 1]} {anno}\n\n"
           f"{len(recs)} messaggi · {len(by_chat)} chat\n\n")
    for safe, n in sorted(files, key=lambda x: -x[1]):
        idx += f"- [[{safe}]] — {n} messaggi\n"
    with open(os.path.join(outdir, "_index.md"), "w", encoding="utf-8") as f:
        f.write(idx)
    print(f"Second brain aggiornato: {outdir} ({len(files)} chat, {len(recs)} messaggi)")


def do_schedule():
    plist = os.path.expanduser("~/Library/LaunchAgents/com.masciadri.gencity-weekly.plist")
    label = "com.masciadri.gencity-weekly"
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>{label}</string>
	<key>ProgramArguments</key>
	<array>
		<string>/bin/bash</string>
		<string>{HERE}/weekly-run.sh</string>
	</array>
	<key>StartCalendarInterval</key>
	<dict>
		<key>Weekday</key>
		<integer>5</integer>
		<key>Hour</key>
		<integer>18</integer>
		<key>Minute</key>
		<integer>30</integer>
	</dict>
	<key>Nice</key>
	<integer>10</integer>
	<key>StandardOutPath</key>
	<string>/Users/marcomasciadri/Library/Logs/gencity-weekly.log</string>
	<key>StandardErrorPath</key>
	<string>/Users/marcomasciadri/Library/Logs/gencity-weekly.log</string>
</dict>
</plist>
"""
    with open(plist, "w") as f:
        f.write(content)
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{label}"], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", plist], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"Agente settimanale installato: ogni venerdì 18:30 → {plist}")
        print("  genera: PDF mensile aggiornato + file .md del mese in brain/")
    else:
        print("Errore bootstrap:", (r.stderr or "")[:200])


def main():
    ap = argparse.ArgumentParser(description="Archivio storico GenTeam (locale, JSONL)")
    ap.add_argument("--inc", action="store_true", help="solo incremento (ultimi messaggi per chat)")
    ap.add_argument("--search", help="cerca testo nell'archivio")
    ap.add_argument("--chat", help="filtra ricerca per nome chat")
    ap.add_argument("--limit", type=int, default=20, help="risultati mostrati (default 20)")
    ap.add_argument("--export", action="store_true", help="esporta report mensile in PDF")
    ap.add_argument("--month", help="mese da esportare, formato YYYY-MM (default: corrente)")
    ap.add_argument("--out", help="percorso PDF di destinazione (default: reports/report-YYYY-MM.pdf)")
    ap.add_argument("--md", action="store_true", help="genera file .md del mese in brain/ per il secondo brain")
    ap.add_argument("--schedule", action="store_true", help="installa l'agente launchd settimanale (venerdì 18:30)")
    args = ap.parse_args()
    if args.schedule:
        do_schedule()
        return
    if args.export:
        month = args.month or __import__("datetime").datetime.now().strftime("%Y-%m")
        do_export(month, args.out)
        return
    if args.md:
        month = args.month or __import__("datetime").datetime.now().strftime("%Y-%m")
        do_md(month)
        return
    if args.search is not None:
        do_search(args.search, args.chat, args.limit)
        return

    known = load_ids()
    chs = gsk("genteam", "channels", "--server_slug", SERVER_SLUG).get("channels", [])
    total_new = 0
    with open(ARCHIVE, "a", encoding="utf-8") as out:
        for ch in chs:
            cid = ch["id"]
            name = ch.get("display_name") or ch.get("name") or cid
            new = paginate_read(out, cid, known, name, ch.get("channel_type"), inc=args.inc)
            total_new += new
            ths = []
            try:
                ths = gsk("genteam", "threads", "--channel_id", cid).get("threads", [])
            except Exception:
                pass
            tn = 0
            for t in ths:
                if not t.get("reply_count"):
                    continue
                tn += paginate_read(out, t["thread_id"], known, name, "thread", is_thread=True, inc=args.inc)
            print(f"  {name}: +{new} (+{tn} in thread)")
            total_new += tn
    print("TOTALE nuovi:", total_new, "| totale messaggi in archivio:", len(known))


if __name__ == "__main__":
    main()

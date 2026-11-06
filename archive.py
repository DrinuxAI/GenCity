#!/usr/bin/env python3
import argparse
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, "archive.jsonl")
SERVER_SLUG = "genspark"


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


def main():
    ap = argparse.ArgumentParser(description="Archivio storico GenTeam (locale, JSONL)")
    ap.add_argument("--inc", action="store_true", help="solo incremento (ultimi messaggi per chat)")
    ap.add_argument("--search", help="cerca testo nell'archivio")
    ap.add_argument("--chat", help="filtra ricerca per nome chat")
    ap.add_argument("--limit", type=int, default=20, help="risultati mostrati (default 20)")
    args = ap.parse_args()
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

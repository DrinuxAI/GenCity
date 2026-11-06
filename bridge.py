#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SERVER_SLUG = "genspark"
MAX_BUILDINGS = 18
MAX_PUBLIC = 10
DM_WINDOW_DAYS = 21
TZ = ZoneInfo("Europe/Zurich")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data.json")
FULL = "--full" in sys.argv

PROJECTS = {
    "medcloud": {"name": "MedCloud", "color": "#39d0c4"},
    "aurasphera": {"name": "Aurasphera", "color": "#ff6fae"},
    "argus": {"name": "ARGUS — Romanzo", "color": "#8f7bff"},
    "technopark": {"name": "Technopark CH", "color": "#ffb14d"},
    "ufficio": {"name": "Ufficio", "color": "#5c9dff"},
}
TYPE_CYCLE = ["hq", "studio", "lab", "workshop"]


def gsk(*args):
    p = subprocess.run(["gsk", *args], capture_output=True, text=True, timeout=180)
    if p.returncode != 0:
        raise RuntimeError("gsk " + " ".join(args) + " failed: " + p.stderr[:300])
    out = json.loads(p.stdout)
    return out.get("data", {})


def parse_ts(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def hhmm(ts):
    dt = parse_ts(ts)
    return dt.astimezone(TZ).strftime("%H:%M") if dt else ""


def age_min(ts):
    dt = parse_ts(ts)
    if not dt:
        return 1e9
    return (datetime.now(timezone.utc) - dt).total_seconds() / 60


def project_for(name):
    n = name.upper()
    if n.startswith("MED"):
        return "medcloud"
    if "AURA" in n:
        return "aurasphera"
    if "ARGUS" in n:
        return "argus"
    if "TECHNOPARK" in n:
        return "technopark"
    return "ufficio"


def status_for(last_at, unread):
    if unread and unread > 0:
        return "attention"
    a = age_min(last_at)
    if a < 45:
        return "working"
    return "idle"


def trunc(s, n):
    s = (s or "").strip().replace("\n", " ")
    return s[: n - 1] + "…" if len(s) > n else s


TASK_STATUS = {"todo": "da fare", "in_progress": "in corso", "in_review": "in revisione", "done": "fatto"}
TASK_PROGRESS = {"todo": 15, "in_progress": 45, "in_review": 75, "done": 100}


def main():
    channels_data = gsk("genteam", "channels", "--server_slug", SERVER_SLUG)
    chats = channels_data.get("channels", [])
    agents_data = gsk("genteam", "agents", "--server_slug", SERVER_SLUG)
    agents_list = agents_data.get("agents", [])
    try:
        tasks = gsk("genteam", "tasks", "--server_slug", SERVER_SLUG, "--op", "list").get("tasks", [])
    except Exception:
        tasks = []

    public = [c for c in chats if c.get("channel_type") == "public"]
    dms = [
        c for c in chats
        if c.get("channel_type") == "dm"
        and c.get("last_message_at")
        and age_min(c["last_message_at"]) < DM_WINDOW_DAYS * 24 * 60
    ]
    public.sort(key=lambda c: c.get("last_message_at") or "", reverse=True)
    dms.sort(key=lambda c: c.get("last_message_at") or "", reverse=True)
    picked = public[:MAX_PUBLIC]
    for d in dms:
        if len(picked) >= MAX_BUILDINGS:
            break
        picked.append(d)

    used_projects = set()
    out_chats = []
    pub_idx = 0

    for ch in picked:
        cid = ch["id"]
        name = ch.get("display_name") or ch.get("name") or cid
        is_dm = ch.get("channel_type") == "dm"
        unread = ch.get("unread_count", 0) or 0
        last_at = ch.get("last_message_at")

        try:
            members = gsk("genteam", "members", "--channel_id", cid, "--op", "list").get("members", [])
        except Exception:
            members = []
        try:
            read = gsk("genteam", "read", "--channel_id", cid, "--limit", "30")
        except Exception:
            read = {}
        items = read.get("items", [])
        msgs = [it.get("data", {}) for it in items if it.get("kind") == "message_recorded"]

        chat_tasks = [t for t in tasks if t.get("channel_id") == cid]
        human_members = [m for m in members if m.get("actor_type") == "human"]
        agent_members = [m for m in members if m.get("actor_type") == "agent"]
        recent_senders = [m.get("sender_actor_id") for m in msgs if m.get("sender_actor_type") == "agent"]

        chat_agents = []
        if is_dm:
            dm_agent = agent_members[0] if agent_members else None
            if dm_agent:
                aid = dm_agent["actor_id"]
                astatus = status_for(last_at, unread)
                atask = "Ha risposto — da leggere" if unread > 0 else "Ultimo intervento " + (hhmm(last_at) or "—")
                if aid in {t["assignee"]["id"] for t in chat_tasks if t.get("assignee", {}).get("type") == "agent"}:
                    t = next(t for t in chat_tasks if t.get("assignee", {}).get("type") == "agent" and t["assignee"]["id"] == aid)
                    atask = trunc(t.get("title"), 60) + " (" + TASK_STATUS.get(t.get("status"), t.get("status")) + ")"
                    astatus = "working" if t.get("status") in ("in_progress", "in_review") else astatus
                chat_agents.append({
                    "id": aid + "@" + cid,
                    "name": dm_agent.get("display_name") or "Agente",
                    "role": "Agente GenTeam",
                    "status": astatus,
                    "task": atask,
                    "progress": 50 if astatus == "working" else 0,
                })
        else:
            ordered = [aid for aid in recent_senders if aid] + [m["actor_id"] for m in agent_members if m["actor_id"] not in recent_senders]
            seen = set()
            picked_agents = []
            for aid in ordered:
                if aid not in seen and len(picked_agents) < 3:
                    seen.add(aid)
                    picked_agents.append(aid)
            last_agent_msg = {}
            for m in msgs:
                if m.get("sender_actor_type") == "agent":
                    last_agent_msg.setdefault(m.get("sender_actor_id"), m)
            for aid in picked_agents:
                mem = next((m for m in agent_members if m["actor_id"] == aid), None)
                if not mem:
                    continue
                astatus, atask, prog = "idle", "In attesa di attività", 0
                if aid in last_agent_msg:
                    m = last_agent_msg[aid]
                    astatus = "working" if age_min(m.get("sent_at") or last_at) < 45 else "idle"
                    atask = "Ha scritto alle " + hhmm(m.get("ts") or last_at)
                    prog = 50
                for t in chat_tasks:
                    if t.get("assignee", {}).get("type") == "agent" and t["assignee"].get("id") == aid:
                        atask = trunc(t.get("title"), 60) + " (" + TASK_STATUS.get(t.get("status"), t.get("status")) + ")"
                        prog = TASK_PROGRESS.get(t.get("status"), prog)
                        if t.get("status") in ("in_progress", "in_review"):
                            astatus = "working"
                        break
                chat_agents.append({
                    "id": aid + "@" + cid,
                    "name": mem.get("display_name") or "Agente",
                    "role": "Agente GenTeam",
                    "status": astatus,
                    "task": atask,
                    "progress": prog,
                })
            if unread > 0 and human_members:
                chat_agents.append({
                    "id": "human@" + cid,
                    "name": "Tu",
                    "role": "Umano",
                    "status": "attention",
                    "task": trunc(str(unread) + " messaggi non letti — dai un'occhiata", 60),
                    "progress": 0,
                })

        messages = []
        activity = []
        for m in msgs[:12]:
            ts = next((it["ts"] for it in items if it.get("data", {}).get("comet_message_id") == m.get("comet_message_id")), None)
            sender = m.get("sender_display_name") or "?"
            if FULL:
                fid = ("human@" + cid) if m.get("sender_actor_type") == "human" else (m.get("sender_actor_id", "") + "@" + cid)
                messages.append({"from": fid, "text": trunc(m.get("content"), 600), "time": hhmm(ts)})
                activity.append({"time": hhmm(ts), "text": sender + ": " + trunc(m.get("content"), 70)})
            else:
                activity.append({"time": hhmm(ts), "text": "Nuovo messaggio da " + sender})
        if not FULL:
            messages = []

        last_is_human = bool(msgs) and msgs[-1].get("sender_actor_type") == "human"
        needs_marco = bool(unread > 0 and msgs and not last_is_human)
        marco_mentioned = any("marco" in (m.get("content") or "").lower() for m in msgs[-5:])

        if is_dm:
            btype = "studio"
        else:
            btype = TYPE_CYCLE[pub_idx % len(TYPE_CYCLE)]
            pub_idx += 1

        proj = project_for(name)
        used_projects.add(proj)
        out_chats.append({
            "id": cid,
            "name": name,
            "project": proj,
            "type": btype,
            "unread": unread,
            "last_activity": last_at,
            "agents": chat_agents,
            "messages": messages,
            "activity": activity,
            "needs_marco": needs_marco,
            "marco_mentioned": marco_mentioned,
        })

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "full" if FULL else "safe",
        "workspace": SERVER_SLUG,
        "projects": {k: PROJECTS[k] for k in PROJECTS if k in used_projects},
        "chats": out_chats,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("data.json scritto:", OUT)
    print("edifici:", len(out_chats), "| modalità:", out["mode"])


if __name__ == "__main__":
    main()

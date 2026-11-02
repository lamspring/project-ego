"""Persistent event-driven execution for one continuous EGO identity.

Mechanisms adapted from DeepSeek's Super-agent exploration: triggers, threads,
a single router, isolated work-item contexts, direct subscriptions, asynchronous
intervention, and an external watchdog. Workers are execution contexts, not new
personalities and never receive independent beliefs, values, or authority.
"""
from __future__ import annotations
import datetime as dt, json
from ego_core import EgoError, dumps, new_id, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS triggers(
 id TEXT PRIMARY KEY,external_id TEXT,source TEXT NOT NULL,kind TEXT NOT NULL,
 thread_id TEXT NOT NULL,payload TEXT NOT NULL,occurred_at TEXT NOT NULL,created_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN('pending','routed','direct','ignored')),
 work_id TEXT,route_reason TEXT,UNIQUE(source,external_id));
CREATE TABLE IF NOT EXISTS work_items(
 id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,title TEXT NOT NULL,brief TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN('queued','running','waiting','succeeded','failed','cancelled')),
 priority INTEGER NOT NULL,owner TEXT,revision INTEGER NOT NULL DEFAULT 0,
 lease_until TEXT,result TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 last_progress TEXT NOT NULL,deadline TEXT,attempts INTEGER NOT NULL DEFAULT 0,
 superseded_by TEXT,route_reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS work_events(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,work_id TEXT NOT NULL,kind TEXT NOT NULL,
 payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS thread_subscriptions(
 thread_id TEXT NOT NULL,work_id TEXT NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(thread_id,work_id));
CREATE TABLE IF NOT EXISTS trigger_deliveries(
 trigger_id TEXT NOT NULL,work_id TEXT NOT NULL,created_at TEXT NOT NULL,
 consumed_at TEXT,PRIMARY KEY(trigger_id,work_id));
CREATE TABLE IF NOT EXISTS watchdog_observations(
 id TEXT PRIMARY KEY,work_id TEXT,kind TEXT NOT NULL,finding TEXT NOT NULL,
 action TEXT NOT NULL,created_at TEXT NOT NULL);
"""
ACTIVE = ("queued", "running", "waiting")
TERMINAL = ("succeeded", "failed", "cancelled")

def _dt(value): return dt.datetime.fromisoformat(value)
def _after(seconds): return (dt.datetime.fromisoformat(now()) + dt.timedelta(seconds=seconds)).isoformat(timespec="seconds")
def _elapsed(value): return (dt.datetime.fromisoformat(now()) - dt.datetime.fromisoformat(value)).total_seconds()

class Runtime:
 def __init__(self, core):
  self.c=core; self.db=core.db; self.db.executescript(SCHEMA)
  sql=self.db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='thread_subscriptions'").fetchone()[0]
  if "thread_id TEXT PRIMARY KEY" in sql:
   with self.db:
    self.db.execute("ALTER TABLE thread_subscriptions RENAME TO thread_subscriptions_v1")
    self.db.execute("CREATE TABLE thread_subscriptions(thread_id TEXT NOT NULL,work_id TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(thread_id,work_id))")
    self.db.execute("INSERT INTO thread_subscriptions SELECT * FROM thread_subscriptions_v1")
    self.db.execute("DROP TABLE thread_subscriptions_v1")
  self.db.commit()

 def _event(self, work_id, kind, payload):
  self.db.execute("INSERT INTO work_events(work_id,kind,payload,created_at) VALUES(?,?,?,?)", (work_id,kind,dumps(payload),now()))

 def ingest(self, source, kind, thread_id, payload, external_id=None, occurred_at=None):
  if not source.strip() or not kind.strip() or not thread_id.strip(): raise EgoError("source, kind and thread required")
  if not isinstance(payload,dict): raise EgoError("trigger payload must be an object")
  tid=new_id("TRG"); at=now()
  try:
   with self.db:
    self.db.execute("INSERT INTO triggers VALUES(?,?,?,?,?,?,?,?,'pending',NULL,NULL)",(tid,external_id,source,kind,thread_id,dumps(payload),occurred_at or at,at))
    self.c.audit("trigger_ingested",[tid],result=f"{source}:{kind}")
  except Exception as ex:
   if "UNIQUE" in str(ex): raise EgoError("duplicate external trigger") from ex
   raise
  return tid

 def route(self, trigger_id, decision, reason, title=None, brief=None, priority=50):
  if decision not in ("ignore","new","direct"): raise EgoError("decision must be ignore, new or direct")
  if not reason.strip(): raise EgoError("route decision requires a reason")
  tr=self.db.execute("SELECT * FROM triggers WHERE id=?",(trigger_id,)).fetchone()
  if not tr or tr["status"]!="pending": raise EgoError("pending trigger required")
  subscriptions=self.db.execute("SELECT work_id FROM thread_subscriptions WHERE thread_id=?",(tr["thread_id"],)).fetchall()
  if decision=="direct" and not subscriptions: raise EgoError("no worker subscribes to this thread")
  if decision=="new" and (not title or not brief): raise EgoError("new work requires title and brief")
  work_ids=[r["work_id"] for r in subscriptions] if decision=="direct" else []
  work_id=work_ids[0] if work_ids else new_id("WRK"); at=now()
  with self.db:
   if decision=="new":
    self.db.execute("INSERT INTO work_items(id,thread_id,title,brief,state,priority,created_at,updated_at,last_progress,route_reason) VALUES(?,?,?,?, 'queued',?,?,?,?,?)",(work_id,tr["thread_id"],title,brief,int(priority),at,at,at,reason))
    self.db.execute("INSERT INTO thread_subscriptions VALUES(?,?,?)",(tr["thread_id"],work_id,at))
    self._event(work_id,"created",{"trigger_id":trigger_id,"brief":brief})
    work_ids=[work_id]
   if decision=="direct":
    for subscribed in work_ids:
     self.db.execute("INSERT INTO trigger_deliveries(trigger_id,work_id,created_at) VALUES(?,?,?)",(trigger_id,subscribed,at))
     self._event(subscribed,"trigger_direct",{"trigger_id":trigger_id})
   status="ignored" if decision=="ignore" else decision if decision=="direct" else "routed"
   self.db.execute("UPDATE triggers SET status=?,work_id=?,route_reason=? WHERE id=?",(status,None if decision=="ignore" else work_id,reason,trigger_id))
   self.c.audit("trigger_routed",[trigger_id]+work_ids if decision!="ignore" else [trigger_id],result=decision)
  return {"trigger_id":trigger_id,"decision":decision,"work_id":None if decision=="ignore" else work_id,"work_ids":work_ids}

 def claim(self, worker, lease_seconds=300, work_id=None):
  if not worker.strip() or lease_seconds<30: raise EgoError("worker and lease >=30 seconds required")
  # IMMEDIATE serializes selection and claim across independent worker processes.
  self.db.execute("BEGIN IMMEDIATE")
  try:
   if work_id:
    r=self.db.execute("SELECT * FROM work_items WHERE id=? AND state='queued'",(work_id,)).fetchone()
   else:
    r=self.db.execute("SELECT * FROM work_items WHERE state='queued' ORDER BY priority DESC,created_at LIMIT 1").fetchone()
   if not r: self.db.rollback(); return None
   at=now(); lease=_after(lease_seconds); revision=r["revision"]+1
   changed=self.db.execute("UPDATE work_items SET state='running',owner=?,revision=?,lease_until=?,updated_at=?,last_progress=?,attempts=attempts+1 WHERE id=? AND state='queued' AND revision=?",(worker,revision,lease,at,at,r["id"],r["revision"])).rowcount
   if changed!=1: raise EgoError("work claim conflict")
   self._event(r["id"],"claimed",{"worker":worker,"revision":revision,"lease_until":lease})
   self.c.audit("work_claimed",[r["id"],worker],result=f"revision:{revision}")
   self.db.commit()
   return {"work_id":r["id"],"thread_id":r["thread_id"],"title":r["title"],"brief":r["brief"],"revision":revision,"lease_until":lease,"inbox":self.inbox(r["id"],consume=True)}
  except Exception:
   self.db.rollback(); raise

 def _owned(self, work_id, worker, revision):
  r=self.db.execute("SELECT * FROM work_items WHERE id=?",(work_id,)).fetchone()
  if not r or r["state"]!="running" or r["owner"]!=worker or r["revision"]!=revision: raise EgoError("stale or unowned worker execution")
  if _dt(r["lease_until"])<=_dt(now()): raise EgoError("worker lease expired")
  return r

 def heartbeat(self, work_id, worker, revision, progress, lease_seconds=300):
  if not progress.strip(): raise EgoError("progress description required")
  self._owned(work_id,worker,revision)
  with self.db:
   self.db.execute("UPDATE work_items SET lease_until=?,last_progress=?,updated_at=? WHERE id=?",(_after(lease_seconds),now(),now(),work_id))
   self._event(work_id,"progress",{"worker":worker,"revision":revision,"progress":progress})
  return {"work_id":work_id,"lease_seconds":lease_seconds}

 def finish(self, work_id, worker, revision, outcome, result):
  if outcome not in ("succeeded","failed","waiting"): raise EgoError("outcome must be succeeded, failed or waiting")
  if not isinstance(result,dict) or not result.get("summary"): raise EgoError("result summary required")
  self._owned(work_id,worker,revision)
  with self.db:
   self.db.execute("UPDATE work_items SET state=?,owner=NULL,lease_until=NULL,result=?,updated_at=?,last_progress=? WHERE id=?",(outcome,dumps(result),now(),now(),work_id))
   if outcome in TERMINAL: self.db.execute("DELETE FROM thread_subscriptions WHERE work_id=?",(work_id,))
   self._event(work_id,outcome,result)
   self.c.audit("work_finished",[work_id,worker],result=outcome)
  return {"work_id":work_id,"state":outcome,"result":result}

 def intervene(self, work_id, action, actor="owner", reason="", brief=None):
  if action not in ("redirect","pause","resume","cancel"): raise EgoError("invalid intervention")
  if not reason.strip(): raise EgoError("intervention requires a reason")
  r=self.db.execute("SELECT * FROM work_items WHERE id=?",(work_id,)).fetchone()
  if not r: raise EgoError("work item not found")
  if action=="resume" and r["state"]!="waiting": raise EgoError("only waiting work can resume")
  if action!="resume" and r["state"] not in ACTIVE: raise EgoError("active work required")
  with self.db:
   if action=="cancel":
    self.db.execute("UPDATE work_items SET state='cancelled',owner=NULL,lease_until=NULL,result=?,updated_at=?,revision=revision+1 WHERE id=?",(dumps({"summary":reason,"intervened_by":actor}),now(),work_id))
    self.db.execute("DELETE FROM thread_subscriptions WHERE work_id=?",(work_id,))
   elif action=="pause":
    self.db.execute("UPDATE work_items SET state='waiting',owner=NULL,lease_until=NULL,updated_at=?,revision=revision+1 WHERE id=?",(now(),work_id))
   else:
    new_brief=brief if action=="redirect" else r["brief"]
    if action=="redirect" and not new_brief: raise EgoError("redirect requires replacement brief")
    self.db.execute("UPDATE work_items SET state='queued',brief=?,owner=NULL,lease_until=NULL,updated_at=?,revision=revision+1 WHERE id=?",(new_brief,now(),work_id))
   self._event(work_id,"intervention",{"action":action,"actor":actor,"reason":reason,"brief":brief})
   self.c.audit("work_intervened",[work_id],result=action,actor=actor)
  return {"work_id":work_id,"action":action}

 def inbox(self, work_id, consume=False):
  rows=self.db.execute("SELECT t.* FROM trigger_deliveries d JOIN triggers t ON t.id=d.trigger_id WHERE d.work_id=? AND d.consumed_at IS NULL ORDER BY t.created_at",(work_id,)).fetchall()
  result=[{"trigger_id":r["id"],"source":r["source"],"kind":r["kind"],"payload":json.loads(r["payload"]),"occurred_at":r["occurred_at"]} for r in rows]
  if consume and rows:
   with self.db:
    for r in rows: self.db.execute("UPDATE trigger_deliveries SET consumed_at=? WHERE trigger_id=? AND work_id=?",(now(),r["id"],work_id))
  return result

 def _inline_payload(self, raw, limit=500):
  payload=json.loads(raw); text=payload.get("text")
  if isinstance(text,str) and len(text)>limit:
   payload=dict(payload); payload["text"]=text[:limit]; payload["spilled_chars"]=len(text)-limit
   payload["spill_note"]="内容已截断；用 recall-trigger 和 Trigger ID 读取完整原文"
  return payload

 def recall_trigger(self, trigger_id):
  r=self.db.execute("SELECT * FROM triggers WHERE id=?",(trigger_id,)).fetchone()
  if not r: raise EgoError("trigger not found")
  result=dict(r); result["payload"]=json.loads(r["payload"])
  result["subscribed_work_ids"]=[x["work_id"] for x in self.db.execute("SELECT work_id FROM thread_subscriptions WHERE thread_id=?",(r["thread_id"],))]
  return result

 def recall(self, work_id):
  r=self.db.execute("SELECT * FROM work_items WHERE id=?",(work_id,)).fetchone()
  if not r: raise EgoError("work item not found")
  triggers=[dict(x) for x in self.db.execute("SELECT * FROM triggers WHERE thread_id=? ORDER BY created_at",(r["thread_id"],))]
  events=[dict(x) for x in self.db.execute("SELECT * FROM work_events WHERE work_id=? ORDER BY seq",(work_id,))]
  for t in triggers: t["payload"]=self._inline_payload(t["payload"])
  for e in events: e["payload"]=self._inline_payload(e["payload"])
  subscriptions=[x["work_id"] for x in self.db.execute("SELECT work_id FROM thread_subscriptions WHERE thread_id=?",(r["thread_id"],))]
  return {"work":dict(r),"thread_id":r["thread_id"],"triggers":triggers,"events":events,"subscribed_work_ids":subscriptions,"identity":"ego-a","context_scope":"execution_only"}

 def watchdog(self, stale_seconds=600):
  observations=[]
  for r in self.db.execute("SELECT * FROM work_items WHERE state IN('queued','running','waiting')"):
   finding=None; action="observe"; kind="no_progress"
   if r["state"]=="running" and r["lease_until"] and _dt(r["lease_until"])<=_dt(now()):
    finding=f"worker lease expired; last revision {r['revision']}"; action="requeue"; kind="expired_lease"
   elif _elapsed(r["last_progress"])>=stale_seconds: finding=f"no progress for at least {stale_seconds} seconds"
   if not finding: continue
   oid=new_id("WDO")
   with self.db:
    if action=="requeue":
     self.db.execute("UPDATE work_items SET state='queued',owner=NULL,lease_until=NULL,revision=revision+1,updated_at=? WHERE id=?",(now(),r["id"]))
     self._event(r["id"],"watchdog_requeue",{"observation_id":oid,"finding":finding})
    self.db.execute("INSERT INTO watchdog_observations VALUES(?,?,?,?,?,?)",(oid,r["id"],kind,finding,action,now()))
    self.c.audit("watchdog_observation",[oid,r["id"]],result=action)
   observations.append({"id":oid,"work_id":r["id"],"kind":kind,"action":action,"finding":finding})
  return observations

 def status(self):
  states={r["state"]:r["n"] for r in self.db.execute("SELECT state,COUNT(*) n FROM work_items GROUP BY state")}
  return {"identity":"ego-a","triggers":self.db.execute("SELECT COUNT(*) FROM triggers").fetchone()[0],"work_items":states,"pending_triggers":self.db.execute("SELECT COUNT(*) FROM triggers WHERE status='pending'").fetchone()[0],"open_watchdog_observations":self.db.execute("SELECT COUNT(*) FROM watchdog_observations").fetchone()[0]}

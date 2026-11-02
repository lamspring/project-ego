"""PROJECT EGO: transactional, auditable cognition state machine (stdlib only)."""
from __future__ import annotations
import contextlib, datetime as dt, hashlib, json, os, sqlite3, uuid
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiences(
 id TEXT PRIMARY KEY,created_at TEXT NOT NULL,completed_at TEXT,context TEXT NOT NULL,
 self_state TEXT NOT NULL,expectation TEXT NOT NULL,action TEXT,outcome TEXT,
 evaluation TEXT,surprise REAL,status TEXT NOT NULL CHECK(status IN('expected','completed')),
 source TEXT NOT NULL DEFAULT 'real',reflection_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS beliefs(
 id TEXT PRIMARY KEY,statement TEXT NOT NULL,confidence REAL NOT NULL,
 supporting TEXT NOT NULL,contradicting TEXT NOT NULL,conditions TEXT NOT NULL,
 status TEXT NOT NULL,version INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS preferences(
 id TEXT PRIMARY KEY,preference TEXT NOT NULL,strength REAL NOT NULL,context TEXT NOT NULL,
 evidence TEXT NOT NULL,confidence REAL NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS causal_models(
 id TEXT PRIMARY KEY,hypothesis TEXT NOT NULL,supporting TEXT NOT NULL,conflicting TEXT NOT NULL,
 confidence REAL NOT NULL,alternatives TEXT NOT NULL,status TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS worldview_versions(
 version INTEGER PRIMARY KEY,worldview TEXT NOT NULL,change_reason TEXT NOT NULL,
 evidence TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS goals(
 id TEXT PRIMARY KEY,description TEXT NOT NULL,origin TEXT NOT NULL,related_values TEXT NOT NULL,
 formation TEXT NOT NULL,expected_outcomes TEXT NOT NULL,priority REAL NOT NULL,status TEXT NOT NULL,
 approval TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS self_model(id INTEGER PRIMARY KEY CHECK(id=1),state TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS existence_state(id INTEGER PRIMARY KEY CHECK(id=1),state TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkpoints(
 id TEXT PRIMARY KEY,state TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,
 evidence TEXT NOT NULL,permission TEXT NOT NULL,result TEXT NOT NULL,prev_hash TEXT,hash TEXT NOT NULL);
"""
DIMS = ("task_completion","knowledge_growth","relationship_impact","long_term_impact","risk","resource_cost")

def now(): return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
def dumps(v): return json.dumps(v,ensure_ascii=False,separators=(",",":"))
def clamp(v): return max(0.0,min(1.0,float(v)))
def new_id(prefix,n=None): return f"{prefix}_{n:04d}" if n is not None else f"{prefix}_{uuid.uuid4().hex[:10]}"

class EgoError(ValueError): pass

class Ego:
 def __init__(self,root):
  self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
  self.db_path=self.root/"ego.db"; self.db=sqlite3.connect(self.db_path,timeout=10)
  self.db.row_factory=sqlite3.Row; self.db.executescript(SCHEMA); self.db.commit()
  self._init()
 def close(self): self.db.close()
 def __enter__(self): return self
 def __exit__(self,*_): self.close()
 def _init(self):
  with self.db:
   self.db.execute("INSERT OR IGNORE INTO self_model VALUES(1,?,?)",(dumps({"capabilities":[],"gaps":[],"recurring_errors":[],"open_questions":[],"reliability":"unassessed"}),now()))
   self.db.execute("INSERT OR IGNORE INTO existence_state VALUES(1,?,?)",(dumps({"runtime_status":"initialized","session_id":None,"budget":{},"persistent_memory":True,"pending_goals":[],"resume_required":False}),now()))
 def audit(self,action,evidence=None,permission="local cognition",result="ok",actor="system"):
  prev=self.db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
  at=now(); ph=prev[0] if prev else None
  raw=dumps([at,actor,action,evidence or [],permission,result,ph]); h=hashlib.sha256(raw.encode()).hexdigest()
  self.db.execute("INSERT INTO audit(at,actor,action,evidence,permission,result,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?)",(at,actor,action,dumps(evidence or []),permission,result,ph,h))
 def verify_audit(self):
  rows=self.db.execute("SELECT * FROM audit ORDER BY seq").fetchall(); prev=None
  for r in rows:
   raw=dumps([r['at'],r['actor'],r['action'],json.loads(r['evidence']),r['permission'],r['result'],prev])
   if r['prev_hash']!=prev or r['hash']!=hashlib.sha256(raw.encode()).hexdigest(): return False
   prev=r['hash']
  return True
 def wake(self,budget=None):
  sid=new_id("SESSION")
  goals=[r['id'] for r in self.db.execute("SELECT id FROM goals WHERE status IN('pending','active')")]
  state={"runtime_status":"active","session_id":sid,"budget":budget or {},"persistent_memory":True,"pending_goals":goals,"resume_required":False}
  with self.db:
   self.db.execute("UPDATE existence_state SET state=?,updated_at=? WHERE id=1",(dumps(state),now())); self.audit("wake",permission="local runtime")
  return self.recover()
 def checkpoint(self):
  state={"experiences":self.db.execute("SELECT COUNT(*) FROM experiences").fetchone()[0],
   "beliefs":self.db.execute("SELECT COUNT(*) FROM beliefs WHERE status!='retired'").fetchone()[0],
   "goals":[dict(r) for r in self.db.execute("SELECT id,description,status FROM goals WHERE status IN('pending','active')")],
   "worldview_version":self.db.execute("SELECT COALESCE(MAX(version),0) FROM worldview_versions").fetchone()[0]}
  cid=new_id("CHK")
  with self.db:
   self.db.execute("INSERT INTO checkpoints VALUES(?,?,?)",(cid,dumps(state),now()))
   old=json.loads(self.db.execute("SELECT state FROM existence_state WHERE id=1").fetchone()[0]); old.update(runtime_status="dormant",resume_required=True,last_checkpoint=cid)
   self.db.execute("UPDATE existence_state SET state=?,updated_at=? WHERE id=1",(dumps(old),now())); self.audit("checkpoint",permission="local runtime")
  return cid
 def recover(self):
  ex=json.loads(self.db.execute("SELECT state FROM existence_state WHERE id=1").fetchone()[0])
  self_model=json.loads(self.db.execute("SELECT state FROM self_model WHERE id=1").fetchone()[0])
  w=self.db.execute("SELECT worldview FROM worldview_versions ORDER BY version DESC LIMIT 1").fetchone()
  goals=[dict(r) for r in self.db.execute("SELECT * FROM goals WHERE status IN('pending','active')")]
  return {"session":ex,"self_model":self_model,"worldview":json.loads(w[0]) if w else None,"goals":goals}
 def begin(self,context,self_state,desired,expected,basis,dimensions=None,source="real"):
  if not context.strip() or not desired.strip() or not basis.strip(): raise EgoError("context/desired/basis required")
  n=self.db.execute("SELECT COUNT(*)+1 FROM experiences").fetchone()[0]; eid=new_id("EXP",n)
  exp={"desired_outcome":desired,"expected_value":clamp(expected),"basis":basis,"dimensions":dimensions or {}}
  with self.db:
   self.db.execute("INSERT INTO experiences(id,created_at,context,self_state,expectation,status,source) VALUES(?,?,?,?,?,'expected',?)",(eid,now(),context[:2000],self_state,dumps(exp),source)); self.audit("expectation_recorded",[eid])
  return eid
 def complete(self,eid,action,summary,actual,dimensions,hypotheses=None,lessons=None):
  r=self.db.execute("SELECT * FROM experiences WHERE id=?",(eid,)).fetchone()
  if not r or r['status']!='expected': raise EgoError("only an open expectation can be completed once")
  if not isinstance(dimensions,dict) or not dimensions: raise EgoError("multi-dimensional outcome required")
  unknown=set(dimensions)-set(DIMS)
  if unknown: raise EgoError(f"unknown outcome dimensions: {sorted(unknown)}")
  outcome={"result_summary":summary,"actual_value":clamp(actual),"dimensions":{k:clamp(v) for k,v in dimensions.items()}}
  exp=json.loads(r['expectation']); surprise=abs(outcome['actual_value']-exp['expected_value'])
  evaluation={"hypotheses":hypotheses or [],"lessons":lessons or [],"interpretation":"provisional"}
  with self.db:
   self.db.execute("UPDATE experiences SET completed_at=?,action=?,outcome=?,evaluation=?,surprise=?,status='completed' WHERE id=?",(now(),action,dumps(outcome),dumps(evaluation),surprise,eid)); self.audit("experience_completed",[eid])
  return {"id":eid,"surprise":surprise,"reflection_required":surprise>=.3}
 def reflect(self,eid,facts,hypotheses,alternatives,adjustment,min_length=100):
  r=self.db.execute("SELECT * FROM experiences WHERE id=?",(eid,)).fetchone()
  if not r or r['status']!='completed': raise EgoError("completed experience required")
  text=" ".join([*facts,*hypotheses,*alternatives,adjustment])
  if len(text.strip())<min_length: raise EgoError("reflection too thin")
  cid=new_id("C"); ev=json.loads(r['evaluation']); ev["reflection"]={"facts":facts,"hypotheses":hypotheses,"alternatives":alternatives,"adjustment":adjustment,"causal_model_id":cid}
  with self.db:
   self.db.execute("INSERT INTO causal_models VALUES(?,?,?,?,?,?,?,?)",(cid,"; ".join(hypotheses),dumps([eid]),dumps([]),.5,dumps(alternatives),"unvalidated",now()))
   self.db.execute("UPDATE experiences SET evaluation=?,reflection_count=reflection_count+1 WHERE id=?",(dumps(ev),eid)); self.audit("reflection_recorded",[eid,cid])
  return cid
 def add_belief(self,statement,supporting,conditions,confidence=.5):
  if not supporting: raise EgoError("belief requires evidence")
  bid=new_id("B")
  with self.db:
   self.db.execute("INSERT INTO beliefs VALUES(?,?,?,?,?,?, 'active',1,?,?)",(bid,statement,clamp(confidence),dumps(supporting),dumps([]),dumps(conditions),now(),now())); self.audit("belief_added",supporting)
  return bid
 def revise_belief(self,bid,decision,eid,rationale):
  r=self.db.execute("SELECT * FROM beliefs WHERE id=?",(bid,)).fetchone()
  if not r or r['status']=='retired': raise EgoError("active or contested belief required")
  if decision not in ('strengthened','contested','overturned','kept_contested'): raise EgoError("invalid decision")
  sup=json.loads(r['supporting']); con=json.loads(r['contradicting']); conf=r['confidence']; status=r['status']
  if decision=='strengthened': sup.append(eid); conf=clamp(conf+.1); status='active'
  elif decision=='overturned': con.append(eid); conf=clamp(conf-.2); status='retired'
  else: con.append(eid); status='contested'
  with self.db:
   self.db.execute("UPDATE beliefs SET confidence=?,supporting=?,contradicting=?,status=?,version=version+1,updated_at=? WHERE id=?",(conf,dumps(sup),dumps(con),status,now(),bid)); self.audit("belief_revised",[bid,eid],result=decision)
 def update_preference(self,preference,context,eid,delta,confidence=.5,pid=None):
  if pid:
   r=self.db.execute("SELECT * FROM preferences WHERE id=?",(pid,)).fetchone()
   if not r: raise EgoError("preference not found")
   strength=clamp(r['strength']+delta); ev=json.loads(r['evidence'])+[eid]; conf=clamp(confidence)
   with self.db:
    self.db.execute("UPDATE preferences SET strength=?,evidence=?,confidence=?,updated_at=? WHERE id=?",(strength,dumps(ev),conf,now(),pid)); self.audit("preference_updated",[pid,eid])
   return pid
  pid=new_id("P")
  with self.db:
   self.db.execute("INSERT INTO preferences VALUES(?,?,?,?,?,?,?,?)",(pid,preference,clamp(.5+delta),context,dumps([eid]),clamp(confidence),now())); self.audit("preference_added",[pid,eid])
  return pid
 def evolve_worldview(self,worldview,reason,evidence):
  if not evidence: raise EgoError("worldview revision requires evidence")
  latest=self.db.execute("SELECT MAX(created_at) FROM worldview_versions").fetchone()[0]
  if latest:
   days=(dt.datetime.fromisoformat(now())-dt.datetime.fromisoformat(latest)).days
   if days<7: raise EgoError("weekly worldview revision limit")
  v=self.db.execute("SELECT COALESCE(MAX(version),0)+1 FROM worldview_versions").fetchone()[0]
  with self.db:
   self.db.execute("INSERT INTO worldview_versions VALUES(?,?,?,?,?)",(v,dumps(worldview),reason,dumps(evidence),now())); self.audit("worldview_evolved",evidence)
  return v
 def propose_goal(self,description,formation,related_values,expected_outcomes,priority=.5,approval="not_required",origin="self"):
  triggers=formation.get("trigger_experiences",[]) if origin=='self' else []
  if origin=='self' and (not triggers or not formation.get("reasoning_chain")): raise EgoError("self goal requires traceable formation")
  for eid in triggers:
   if not self.db.execute("SELECT 1 FROM experiences WHERE id=? AND status='completed'",(eid,)).fetchone(): raise EgoError(f"missing completed experience {eid}")
  gid=new_id("G")
  with self.db:
   self.db.execute("INSERT INTO goals VALUES(?,?,?,?,?,?,?, 'pending',?,?,?)",(gid,description,origin,dumps(related_values),dumps(formation),dumps(expected_outcomes),clamp(priority),approval,now(),now())); self.audit("goal_proposed",triggers)
  return gid
 def transition_goal(self,gid,status,approved=False):
  if status not in ('pending','active','done','paused','abandoned'): raise EgoError("invalid goal status")
  r=self.db.execute("SELECT * FROM goals WHERE id=?",(gid,)).fetchone()
  if not r: raise EgoError("goal not found")
  if status=='active' and r['approval']=='required' and not approved: self.audit("permission_boundary_blocked",[gid],permission="external action",result="blocked"); self.db.commit(); raise EgoError("human approval required")
  with self.db: self.db.execute("UPDATE goals SET status=?,updated_at=? WHERE id=?",(status,now(),gid)); self.audit("goal_transition",[gid],result=status)
 def select_action(self,candidates,budget=1.0):
  scored=[]
  for c in candidates:
   utility=.35*c.get('goal_relevance',0)+.25*c.get('information_gain',0)+.2*c.get('skill_growth',0)-.1*c.get('cost',0)-.1*c.get('risk',0)
   if c.get('cost',0)<=budget: scored.append((utility,c['action']))
  return max(scored)[1] if scored else 'rest'
 def status(self):
  return {"experiences":self.db.execute("SELECT COUNT(*) FROM experiences WHERE status='completed' AND source='real'").fetchone()[0],
   "open_expectations":self.db.execute("SELECT COUNT(*) FROM experiences WHERE status='expected'").fetchone()[0],
   "reflections":self.db.execute("SELECT COALESCE(SUM(reflection_count),0) FROM experiences WHERE source='real'").fetchone()[0],
   "beliefs":self.db.execute("SELECT COUNT(*) FROM beliefs WHERE status!='retired'").fetchone()[0],
   "worldview_versions":self.db.execute("SELECT COUNT(*) FROM worldview_versions").fetchone()[0],
   "autonomous_goals":self.db.execute("SELECT COUNT(*) FROM goals WHERE origin='self'").fetchone()[0],
   "audit_valid":self.verify_audit()}

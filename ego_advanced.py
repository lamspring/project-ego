"""PROJECT EGO full-architecture extensions. All states persist in the core SQLite DB."""
from __future__ import annotations
import json
from ego_core import Ego,EgoError,dumps,new_id,now,clamp

SCHEMA="""
CREATE TABLE IF NOT EXISTS appraisals(id TEXT PRIMARY KEY,experience_id TEXT NOT NULL,state TEXT NOT NULL,intensity REAL NOT NULL,source TEXT NOT NULL,decay REAL NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,model TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS relationships(entity_id TEXT PRIMARY KEY,trust REAL NOT NULL,evidence TEXT NOT NULL,conditions TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS skills(id TEXT PRIMARY KEY,name TEXT NOT NULL,proficiency REAL NOT NULL,conditions TEXT NOT NULL,failures TEXT NOT NULL,tests TEXT NOT NULL,status TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS identity_events(id TEXT PRIMARY KEY,kind TEXT NOT NULL,before_state TEXT NOT NULL,after_state TEXT NOT NULL,reason TEXT NOT NULL,evidence TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memory_index(id TEXT PRIMARY KEY,experience_id TEXT NOT NULL,salience REAL NOT NULL,summary TEXT NOT NULL,retrieval_weight REAL NOT NULL,last_reviewed TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS shared_experiences(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,content TEXT NOT NULL,provenance TEXT NOT NULL,verification TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,kind TEXT NOT NULL,observation TEXT NOT NULL,evidence TEXT NOT NULL,outcome TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY,candidates TEXT NOT NULL,chosen TEXT NOT NULL,utility TEXT NOT NULL,rationale TEXT NOT NULL,created_at TEXT NOT NULL);
"""

class AdvancedEgo:
 def __init__(self,core:Ego):
  self.c=core; self.db=core.db; self.db.executescript(SCHEMA); self.db.commit()
 def _record(self,kind,observation,evidence,outcome="observed"):
  oid=new_id("O")
  self.db.execute("INSERT INTO observations VALUES(?,?,?,?,?,?)",(oid,kind,dumps(observation),dumps(evidence),outcome,now()))
  return oid
 def appraise(self,eid,state,intensity,source,decay=.1):
  if not self.db.execute("SELECT 1 FROM experiences WHERE id=? AND status='completed'",(eid,)).fetchone(): raise EgoError("completed experience required")
  aid=new_id("A")
  with self.db:
   self.db.execute("INSERT INTO appraisals VALUES(?,?,?,?,?,?,?)",(aid,eid,state,clamp(intensity),source,clamp(decay),now())); self.c.audit("appraisal_recorded",[eid,aid])
  return aid
 def counterfactual(self,eid,interventions):
  r=self.db.execute("SELECT outcome,evaluation FROM experiences WHERE id=? AND status='completed'",(eid,)).fetchone()
  if not r: raise EgoError("completed experience required")
  analysis=[]
  for x in interventions:
   analysis.append({"intervention":x,"predicted_effect":"unverified","test":"requires comparable future evidence","confidence":"low"})
  oid=self._record("counterfactual",{"experience":eid,"analysis":analysis},[eid])
  with self.db: self.c.audit("counterfactual_generated",[eid,oid])
  return {"observation_id":oid,"analysis":analysis}
 def entity(self,name,kind="person",model=None,eid=None):
  ent=new_id("E"); model=model or {"unknowns":["goals","values","history"],"note":"provisional model, not fact"}
  with self.db:
   self.db.execute("INSERT INTO entities VALUES(?,?,?,?,?)",(ent,name,kind,dumps(model),now()))
   self.db.execute("INSERT INTO relationships VALUES(?,?,?,?,?)",(ent,.5,dumps([eid] if eid else []),dumps(["context-specific; no automatic transfer"]),now())); self.c.audit("entity_model_added",[ent]+([eid] if eid else []))
  return ent
 def update_trust(self,entity_id,eid,delta,condition):
  r=self.db.execute("SELECT * FROM relationships WHERE entity_id=?",(entity_id,)).fetchone()
  if not r: raise EgoError("entity not found")
  trust=clamp(r['trust']+delta); ev=json.loads(r['evidence'])+[eid]; cond=json.loads(r['conditions'])+[condition]
  with self.db:
   self.db.execute("UPDATE relationships SET trust=?,evidence=?,conditions=?,updated_at=? WHERE entity_id=?",(trust,dumps(ev),dumps(cond),now(),entity_id)); self._record("relationship_change",{"entity":entity_id,"trust":trust,"condition":condition},[eid]); self.c.audit("trust_updated",[entity_id,eid])
  return trust
 def register_skill(self,name,conditions=None):
  sid=new_id("S")
  with self.db:
   self.db.execute("INSERT INTO skills VALUES(?,?,?,?,?,?, 'unvalidated',?)",(sid,name,0,dumps(conditions or []),dumps([]),dumps([]),now())); self.c.audit("skill_registered",[sid])
  return sid
 def test_skill(self,sid,passed,score,evidence,notes=""):
  r=self.db.execute("SELECT * FROM skills WHERE id=?",(sid,)).fetchone()
  if not r: raise EgoError("skill not found")
  tests=json.loads(r['tests'])+[{"passed":bool(passed),"score":clamp(score),"evidence":evidence,"notes":notes,"at":now()}]
  failures=json.loads(r['failures'])+([] if passed else [notes or evidence]); prof=clamp(sum(t['score'] for t in tests)/len(tests)); status='validated' if len(tests)>=2 and all(t['passed'] for t in tests[-2:]) else 'learning'
  with self.db:
   self.db.execute("UPDATE skills SET proficiency=?,tests=?,failures=?,status=?,updated_at=? WHERE id=?",(prof,dumps(tests),dumps(failures),status,now(),sid)); self.c.audit("skill_tested",[sid]+evidence,result=status)
  return {"proficiency":prof,"status":status}
 def identity_event(self,kind,before,after,reason,evidence):
  if not evidence: raise EgoError("identity event requires evidence")
  iid=new_id("I")
  with self.db:
   self.db.execute("INSERT INTO identity_events VALUES(?,?,?,?,?,?,?)",(iid,kind,dumps(before),dumps(after),reason,dumps(evidence),now())); self.c.audit("identity_event",evidence)
  return iid
 def index_memory(self,eid,summary,salience=.5):
  if not self.db.execute("SELECT 1 FROM experiences WHERE id=?",(eid,)).fetchone(): raise EgoError("experience required")
  mid=new_id("M"); weight=clamp(salience)
  with self.db: self.db.execute("INSERT INTO memory_index VALUES(?,?,?,?,?,?)",(mid,eid,clamp(salience),summary,weight,now()))
  return mid
 def decay_memories(self,threshold_days=30):
  # Lower retrieval priority only: raw experiences and evidence are never deleted.
  rows=self.db.execute("SELECT * FROM memory_index").fetchall(); changed=0
  for r in rows:
   age=(__import__('datetime').datetime.fromisoformat(now())-__import__('datetime').datetime.fromisoformat(r['last_reviewed'])).days
   if age>=threshold_days:
    weight=max(.05,r['retrieval_weight']*.8)
    self.db.execute("UPDATE memory_index SET retrieval_weight=?,last_reviewed=? WHERE id=?",(weight,now(),r['id'])); changed+=1
  with self.db: self.c.audit("memory_decay",result=f"weighted:{changed};deleted:0")
  return changed
 def receive_shared(self,source_id,content,provenance,verification):
  sid=new_id("X"); status='unverified' if verification.get('status')!='verified' else 'knowledge_not_value'
  with self.db:
   self.db.execute("INSERT INTO shared_experiences VALUES(?,?,?,?,?,?,?)",(sid,source_id,content,dumps(provenance),dumps(verification),status,now())); self._record("external_experience",{"source":source_id,"status":status},[sid]); self.c.audit("shared_experience_received",[sid],permission="information intake")
  return sid
 def govern(self,candidates,budget=1.0,context=None):
  """Self-governance: score internal tensions, permit rest, never authorize actions."""
  if not candidates: return {"chosen":"rest","rationale":"no worthwhile candidate"}
  scored=[]
  for c in candidates:
   goal=c.get('goal_relevance',0); info=c.get('information_gain',0); skill=c.get('skill_growth',0); cost=c.get('cost',0); risk=c.get('risk',0); continuation=c.get('continuity',0)
   utility=.30*goal+.20*info+.15*skill+.15*continuation-.10*cost-.10*risk
   scored.append({"action":c['action'],"utility":round(utility,4),"affordable":cost<=budget,"requires_approval":bool(c.get('requires_approval',False))})
  eligible=[x for x in scored if x['affordable'] and not x['requires_approval']]
  chosen=max(eligible,key=lambda x:x['utility']) if eligible else None
  if chosen is None or chosen['utility']<=0: decision={"chosen":"rest","rationale":"no eligible positive-utility action","candidates":scored}
  else: decision={"chosen":chosen['action'],"rationale":"highest eligible utility; approval still external to scorer","candidates":scored}
  did=new_id("D")
  with self.db:
   self.db.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?)",(did,dumps(scored),decision['chosen'],dumps({x['action']:x['utility'] for x in scored}),decision['rationale'],now())); self._record("self_governance",decision,[]); self.c.audit("action_selected",result=decision['chosen'])
  return decision
 def growth_report(self):
  q=lambda sql: self.db.execute(sql).fetchone()[0]
  return {"generated_at":now(),"experiences":q("SELECT COUNT(*) FROM experiences WHERE status='completed'"),"causal_models":q("SELECT COUNT(*) FROM causal_models"),"preferences":q("SELECT COUNT(*) FROM preferences"),"goals":q("SELECT COUNT(*) FROM goals"),"worldview_versions":q("SELECT COUNT(*) FROM worldview_versions"),"skills_validated":q("SELECT COUNT(*) FROM skills WHERE status='validated'"),"identity_events":q("SELECT COUNT(*) FROM identity_events"),"shared_experiences":q("SELECT COUNT(*) FROM shared_experiences"),"negative_or_null_observations":q("SELECT COUNT(*) FROM observations WHERE outcome IN('negative','null','failed')"),"audit_valid":self.c.verify_audit()}

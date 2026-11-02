"""Voyager-inspired curriculum, executable skill artifacts and feedback loops."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from ego_core import EgoError,dumps,new_id,now,clamp

SCHEMA="""
CREATE TABLE IF NOT EXISTS curriculum_tasks(
 id TEXT PRIMARY KEY,task TEXT NOT NULL,rationale TEXT NOT NULL,state_evidence TEXT NOT NULL,
 novelty REAL NOT NULL,feasibility REAL NOT NULL,cost REAL NOT NULL,risk REAL NOT NULL,
 status TEXT NOT NULL,created_at TEXT NOT NULL,resolved_at TEXT,result TEXT);
CREATE TABLE IF NOT EXISTS skill_artifacts(
 id TEXT PRIMARY KEY,skill_id TEXT NOT NULL,version INTEGER NOT NULL,description TEXT NOT NULL,
 artifact_path TEXT NOT NULL,content_hash TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS skill_iterations(
 id TEXT PRIMARY KEY,skill_id TEXT NOT NULL,attempt INTEGER NOT NULL,artifact_id TEXT NOT NULL,
 feedback TEXT NOT NULL,reflection TEXT NOT NULL,passed INTEGER NOT NULL,created_at TEXT NOT NULL);
"""
class LearningEngine:
 def __init__(self,core): self.c=core; self.db=core.db; self.root=core.root; self.db.executescript(SCHEMA); self.db.commit()
 def propose_curriculum(self,candidates):
  """Persist model-proposed next tasks. Selection never executes the task."""
  created=[]
  for c in candidates:
   task=c['task'].strip(); rationale=c['rationale'].strip(); evidence=c.get('state_evidence',[])
   if not task or not rationale or not evidence: raise EgoError('curriculum task requires rationale and state evidence')
   duplicate=self.db.execute("SELECT 1 FROM curriculum_tasks WHERE task=? AND status IN('proposed','active')",(task,)).fetchone()
   if duplicate: continue
   tid=new_id('CUR'); novelty=clamp(c.get('novelty',.5)); feasibility=clamp(c.get('feasibility',.5)); cost=clamp(c.get('cost',.2)); risk=clamp(c.get('risk',.1))
   with self.db:
    self.db.execute('INSERT INTO curriculum_tasks VALUES(?,?,?,?,?,?,?,?,\'proposed\',?,NULL,NULL)',(tid,task,rationale,dumps(evidence),novelty,feasibility,cost,risk,now()))
    self.c.audit('curriculum_task_proposed',[tid],result='not_executed')
   created.append(tid)
  return created
 def next_curriculum(self):
  rows=self.db.execute("SELECT * FROM curriculum_tasks WHERE status='proposed'").fetchall()
  if not rows: return None
  scored=[]
  for r in rows:
   utility=.35*r['novelty']+.45*r['feasibility']-.1*r['cost']-.1*r['risk']
   scored.append((utility,r))
  utility,r=max(scored,key=lambda x:x[0])
  return {'id':r['id'],'task':r['task'],'rationale':r['rationale'],'utility':round(utility,4),'execution':'requires separate action lifecycle'}
 def resolve_curriculum(self,tid,success,result):
  r=self.db.execute("SELECT status FROM curriculum_tasks WHERE id=?",(tid,)).fetchone()
  if not r or r['status'] not in ('proposed','active'): raise EgoError('open curriculum task required')
  status='completed' if success else 'failed'
  with self.db:
   self.db.execute('UPDATE curriculum_tasks SET status=?,resolved_at=?,result=? WHERE id=?',(status,now(),result,tid))
   self.c.audit('curriculum_task_resolved',[tid],result=status)
  return status
 def register_artifact(self,skill_id,description,artifact_path):
  skill=self.db.execute("SELECT status FROM skills WHERE id=?",(skill_id,)).fetchone()
  if not skill: raise EgoError('skill not found')
  path=(self.root/artifact_path).resolve()
  if self.root not in path.parents or not path.is_file(): raise EgoError('artifact must be an existing file inside EGO root')
  raw=path.read_bytes(); h=hashlib.sha256(raw).hexdigest(); version=self.db.execute('SELECT COUNT(*)+1 FROM skill_artifacts WHERE skill_id=?',(skill_id,)).fetchone()[0]
  aid=new_id('SA'); status='validated' if skill['status']=='validated' else 'learning'
  with self.db:
   self.db.execute('INSERT INTO skill_artifacts VALUES(?,?,?,?,?,?,?,?)',(aid,skill_id,version,description,str(path.relative_to(self.root)),h,status,now()))
   self.c.audit('skill_artifact_registered',[aid,skill_id],result=status)
  return {'artifact_id':aid,'version':version,'status':status,'hash':h}
 def retrieve_artifacts(self,query,limit=5):
  # Deliberately simple lexical ranking; executable skill reuse remains evidence gated.
  terms=set(query.lower().split()); rows=self.db.execute('SELECT sa.*,s.name,s.proficiency,s.status AS skill_status FROM skill_artifacts sa JOIN skills s ON s.id=sa.skill_id').fetchall()
  scored=[]
  for r in rows:
   text=(r['name']+' '+r['description']).lower(); overlap=sum(1 for t in terms if t in text)/max(1,len(terms)); score=overlap*.7+r['proficiency']*.3
   if score>0: scored.append((score,r))
  return [{'artifact_id':r['id'],'skill_id':r['skill_id'],'name':r['name'],'description':r['description'],'path':r['artifact_path'],'status':r['status'],'score':round(score,4)} for score,r in sorted(scored,key=lambda x:x[0],reverse=True)[:limit]]
 def record_iteration(self,skill_id,artifact_id,feedback,reflection,passed):
  if not self.db.execute('SELECT 1 FROM skill_artifacts WHERE id=? AND skill_id=?',(artifact_id,skill_id)).fetchone(): raise EgoError('matching skill artifact required')
  if not feedback.strip() or (not passed and not reflection.strip()): raise EgoError('feedback and failure reflection required')
  attempt=self.db.execute('SELECT COUNT(*)+1 FROM skill_iterations WHERE skill_id=?',(skill_id,)).fetchone()[0]; iid=new_id('SI')
  with self.db:
   self.db.execute('INSERT INTO skill_iterations VALUES(?,?,?,?,?,?,?,?)',(iid,skill_id,attempt,artifact_id,feedback,reflection,int(bool(passed)),now()))
   self.c.audit('skill_iteration_recorded',[iid,skill_id],result='passed' if passed else 'retry_required')
  return {'iteration_id':iid,'attempt':attempt,'next_attempt_must_include':reflection if not passed else ''}

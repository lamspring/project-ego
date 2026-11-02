"""Source-aware, autonomous judgment loop. External claims never become values by intake."""
from __future__ import annotations
import json
from ego_core import EgoError,dumps,new_id,now,clamp

SCHEMA="""
CREATE TABLE IF NOT EXISTS external_inputs(
 id TEXT PRIMARY KEY,source_kind TEXT NOT NULL,source_id TEXT NOT NULL,content TEXT NOT NULL,
 context TEXT NOT NULL,provenance TEXT NOT NULL,source_assessment TEXT NOT NULL,
 parent_input_id TEXT,gap_id TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS judgment_attempts(
 id TEXT PRIMARY KEY,input_id TEXT NOT NULL,prior_input_ids TEXT NOT NULL,facts TEXT NOT NULL,
 hypotheses TEXT NOT NULL,alternatives TEXT NOT NULL,conclusion TEXT NOT NULL,
 confidence REAL NOT NULL,conditions TEXT NOT NULL,gaps TEXT NOT NULL,
 reversible_action TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_gaps(
 id TEXT PRIMARY KEY,input_id TEXT NOT NULL,judgment_id TEXT NOT NULL,question TEXT NOT NULL,
 reason TEXT NOT NULL,route TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,
 answered_at TEXT,answer_input_id TEXT);
"""

class EpistemicLoop:
 def __init__(self,core):
  self.c=core; self.db=core.db; self.db.executescript(SCHEMA); self.db.commit()
 def intake(self,source_kind,source_id,content,context,provenance=None,source_assessment=None,parent_input_id=None,gap_id=None):
  if source_kind not in ('owner','web','agent','direct_experience','other'): raise EgoError('invalid external source kind')
  if not content.strip() or not context.strip(): raise EgoError('external content and context required')
  if parent_input_id and not self.db.execute('SELECT 1 FROM external_inputs WHERE id=?',(parent_input_id,)).fetchone(): raise EgoError('parent input not found')
  if gap_id:
   gap=self.db.execute("SELECT status FROM knowledge_gaps WHERE id=?",(gap_id,)).fetchone()
   if not gap or gap['status']!='open': raise EgoError('open knowledge gap required')
  iid=new_id('SRC'); provenance=provenance or {}; assessment=source_assessment or {}
  # Source metadata remains explicit; authority never substitutes for verification.
  assessment={'credibility':assessment.get('credibility','unassessed'),
   'independent_evidence':assessment.get('independent_evidence',[]),
   'conflicts_of_interest':assessment.get('conflicts_of_interest','unknown'),
   'verifiability':assessment.get('verifiability','unassessed')}
  with self.db:
   self.db.execute('INSERT INTO external_inputs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
    (iid,source_kind,source_id,content,context,dumps(provenance),dumps(assessment),parent_input_id,gap_id,'received_not_adopted',now()))
   if gap_id: self.db.execute("UPDATE knowledge_gaps SET status='answered_requires_rejudgment',answered_at=?,answer_input_id=? WHERE id=?",(now(),iid,gap_id))
   self.c.audit('external_information_received',[iid]+([gap_id] if gap_id else []),permission='information intake',result='not_adopted')
  return {'input_id':iid,'status':'received_not_adopted','requires_judgment':True,'gap_id':gap_id}
 def judge(self,input_id,facts,hypotheses,alternatives,conclusion,confidence,conditions,gaps=None,reversible_action='',prior_input_ids=None):
  if not self.db.execute('SELECT 1 FROM external_inputs WHERE id=?',(input_id,)).fetchone(): raise EgoError('external input required')
  if not facts or not hypotheses or not alternatives or not conclusion.strip() or not conditions: raise EgoError('facts, hypotheses, alternatives, conclusion and conditions required')
  prior_input_ids=prior_input_ids or []
  for prior in prior_input_ids:
   if not self.db.execute('SELECT 1 FROM external_inputs WHERE id=?',(prior,)).fetchone(): raise EgoError(f'prior input not found: {prior}')
  gaps=gaps or []; jid=new_id('J'); status='needs_information' if gaps else 'provisional'
  with self.db:
   self.db.execute('INSERT INTO judgment_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
    (jid,input_id,dumps(prior_input_ids),dumps(facts),dumps(hypotheses),dumps(alternatives),conclusion,clamp(confidence),dumps(conditions),dumps(gaps),reversible_action,status,now()))
   self.db.execute("UPDATE external_inputs SET status=? WHERE id=?",('judged_'+status,input_id))
   self.c.audit('independent_judgment_recorded',[input_id,jid],result=status)
  return {'judgment_id':jid,'status':status,'confidence':clamp(confidence),'gaps':gaps,'cognitive_state_changed':False}
 def request_help(self,judgment_id,question,reason,route='owner'):
  r=self.db.execute("SELECT input_id,status,gaps FROM judgment_attempts WHERE id=?",(judgment_id,)).fetchone()
  if not r or r['status']!='needs_information': raise EgoError('a judgment with unresolved gaps required')
  if route not in ('owner','web','agent','other'): raise EgoError('invalid help route')
  if not question.strip() or not reason.strip(): raise EgoError('specific question and reason required')
  gid=new_id('GAP')
  with self.db:
   self.db.execute('INSERT INTO knowledge_gaps VALUES(?,?,?,?,?,?,\'open\',?,NULL,NULL)',
    (gid,r['input_id'],judgment_id,question,reason,route,now()))
   self.c.audit('knowledge_gap_opened',[gid,judgment_id],permission=f'external help via {route}',result='queued_not_sent')
  return {'gap_id':gid,'status':'open','route':route,'delivery':'not_claimed'}
 def trace(self,input_id):
  source=self.db.execute('SELECT * FROM external_inputs WHERE id=?',(input_id,)).fetchone()
  if not source: raise EgoError('external input not found')
  return {'source':dict(source),
   'judgments':[dict(r) for r in self.db.execute('SELECT * FROM judgment_attempts WHERE input_id=? ORDER BY created_at',(input_id,))],
   'gaps':[dict(r) for r in self.db.execute('SELECT * FROM knowledge_gaps WHERE input_id=? ORDER BY created_at',(input_id,))]}

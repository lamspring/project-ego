"""Local-first memory retrieval and consolidation.

Mechanisms adapted from Mem0, Generative Agents and Letta. The built-in vector
is a hashed character/token n-gram lexical vector, not a neural embedding.
"""
from __future__ import annotations
import datetime as dt,hashlib,json,math,re
from ego_core import EgoError,dumps,new_id,now,clamp

SCHEMA="""
CREATE TABLE IF NOT EXISTS memory_items(
 id TEXT PRIMARY KEY,source_type TEXT NOT NULL,source_id TEXT NOT NULL,kind TEXT NOT NULL,
 content TEXT NOT NULL,entities TEXT NOT NULL,created_at TEXT NOT NULL,last_accessed TEXT NOT NULL,
 importance REAL NOT NULL,retrieval_weight REAL NOT NULL,vector TEXT NOT NULL,vector_model TEXT NOT NULL,
 content_hash TEXT NOT NULL,depth INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,
 UNIQUE(source_type,source_id,content_hash));
CREATE TABLE IF NOT EXISTS memory_blocks(
 label TEXT PRIMARY KEY,content TEXT NOT NULL,char_limit INTEGER NOT NULL,version INTEGER NOT NULL,
 evidence TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memory_block_versions(
 id TEXT PRIMARY KEY,label TEXT NOT NULL,content TEXT NOT NULL,version INTEGER NOT NULL,
 evidence TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reflection_strategies(
 id TEXT PRIMARY KEY,task_key TEXT NOT NULL,experience_id TEXT NOT NULL,strategy TEXT NOT NULL,
 evidence TEXT NOT NULL,created_at TEXT NOT NULL);
"""
DIM=256

def tokens(text):
 words=re.findall(r'[a-zA-Z0-9_]+|[\u4e00-\u9fff]',text.lower())
 bigrams=[''.join(text.lower().replace(' ','')[i:i+2]) for i in range(max(0,len(text.replace(' ',''))-1))]
 return words+bigrams

def vector(text):
 v=[0.0]*DIM
 for token in tokens(text): v[int(hashlib.sha256(token.encode()).hexdigest()[:8],16)%DIM]+=1.0
 norm=math.sqrt(sum(x*x for x in v)) or 1.0
 return [x/norm for x in v]
def cosine(a,b): return sum(x*y for x,y in zip(a,b))
def normalized(values):
 if not values: return {}
 lo,hi=min(values.values()),max(values.values())
 return {k:.5 if hi==lo else (v-lo)/(hi-lo) for k,v in values.items()}
def hours_since(value):
 return max(0,(dt.datetime.fromisoformat(now())-dt.datetime.fromisoformat(value)).total_seconds()/3600)

class MemoryEngine:
 def __init__(self,core): self.c=core; self.db=core.db; self.db.executescript(SCHEMA); self.db.commit()
 def add(self,source_type,source_id,kind,content,entities=None,importance=.5,created_at=None,depth=0):
  if not content.strip(): raise EgoError('memory content required')
  h=hashlib.sha256(content.encode()).hexdigest(); mid=new_id('MEM'); at=created_at or now()
  with self.db:
   self.db.execute('INSERT INTO memory_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,\'active\')',
    (mid,source_type,source_id,kind,content,dumps(entities or []),at,at,clamp(importance),1,dumps(vector(content)),'hashed-ngram-v1',h,depth))
   self.c.audit('memory_indexed',[mid,source_id],result=kind)
  return mid
 def sync(self):
  """Index raw state without changing it; existing unique entries are skipped."""
  count=0
  for r in self.db.execute("SELECT * FROM experiences WHERE status='completed'"):
   content=f"{r['context']} {r['outcome'] or ''} {r['evaluation'] or ''}"
   try: self.add('experience',r['id'],'episode',content,importance=clamp(.35+(r['surprise'] or 0)),created_at=r['completed_at']); count+=1
   except Exception as ex:
    if 'UNIQUE' not in str(ex): raise
  try: sources=self.db.execute('SELECT * FROM external_inputs').fetchall()
  except Exception: sources=[]
  for r in sources:
   try: self.add('external_source',r['id'],'source',r['content']+' '+r['context'],importance=.35,created_at=r['created_at']); count+=1
   except Exception as ex:
    if 'UNIQUE' not in str(ex): raise
  try: judgments=self.db.execute('SELECT * FROM judgment_attempts').fetchall()
  except Exception: judgments=[]
  for r in judgments:
   content=f"{r['conclusion']} 条件:{r['conditions']} 假设:{r['hypotheses']} 替代:{r['alternatives']}"
   try: self.add('judgment',r['id'],'judgment',content,importance=.55,created_at=r['created_at']); count+=1
   except Exception as ex:
    if 'UNIQUE' not in str(ex): raise
  return {'new_items':count,'total':self.db.execute('SELECT COUNT(*) FROM memory_items').fetchone()[0]}
 def search(self,query,limit=8,entities=None,after=None,before=None,kinds=None):
  if not query.strip(): raise EgoError('retrieval query required')
  rows=self.db.execute("SELECT * FROM memory_items WHERE status='active'").fetchall()
  candidates=[]; qv=vector(query)
  for r in rows:
   if after and r['created_at']<after: continue
   if before and r['created_at']>before: continue
   if kinds and r['kind'] not in kinds: continue
   rent=set(json.loads(r['entities']))
   if entities and not rent.intersection(entities): continue
   candidates.append(r)
  if not candidates: return []
  recency={r['id']:.995**hours_since(r['last_accessed']) for r in candidates}
  importance={r['id']:r['importance'] for r in candidates}
  relevance={r['id']:max(0,cosine(qv,json.loads(r['vector']))) for r in candidates}
  rn,ir,rr=normalized(recency),normalized(importance),normalized(relevance)
  scored=[]
  for r in candidates:
   mid=r['id']; score=(.5*rn[mid]+3*rr[mid]+2*ir[mid])*r['retrieval_weight']
   scored.append((score,r,{'recency':rn[mid],'relevance':rr[mid],'importance':ir[mid],'retrieval_weight':r['retrieval_weight']}))
  scored.sort(key=lambda x:x[0],reverse=True); selected=scored[:limit]
  with self.db:
   for _,r,_ in selected: self.db.execute('UPDATE memory_items SET last_accessed=? WHERE id=?',(now(),r['id']))
  return [{'id':r['id'],'source_type':r['source_type'],'source_id':r['source_id'],'kind':r['kind'],'content':r['content'],'score':round(score,5),'signals':signals,'vector_model':'hashed-ngram-v1'} for score,r,signals in selected]
 def consolidate(self,label,content,evidence,char_limit=2000):
  if not evidence or not content.strip(): raise EgoError('consolidation requires content and source evidence')
  for source in evidence:
   if not self.db.execute("SELECT 1 FROM memory_items WHERE source_id=? OR id=?",(source,source)).fetchone(): raise EgoError(f'memory evidence not found: {source}')
  if len(content)>char_limit: raise EgoError('memory block exceeds character limit')
  r=self.db.execute('SELECT version FROM memory_blocks WHERE label=?',(label,)).fetchone(); version=(r[0]+1) if r else 1; vid=new_id('MBV')
  with self.db:
   self.db.execute('INSERT INTO memory_block_versions VALUES(?,?,?,?,?,?)',(vid,label,content,version,dumps(evidence),now()))
   self.db.execute('INSERT INTO memory_blocks VALUES(?,?,?,?,?,?) ON CONFLICT(label) DO UPDATE SET content=excluded.content,char_limit=excluded.char_limit,version=excluded.version,evidence=excluded.evidence,updated_at=excluded.updated_at',(label,content,char_limit,version,dumps(evidence),now()))
   self.add('consolidation',vid,'learned_context',content,importance=.65,depth=1)
   self.c.audit('memory_consolidated',[vid]+evidence,result=f'{label}:v{version}')
  return {'block_id':vid,'label':label,'version':version,'raw_history_preserved':True}
 def record_strategy(self,task_key,experience_id,strategy):
  if not task_key.strip() or not strategy.strip(): raise EgoError('task key and strategy required')
  r=self.db.execute("SELECT evaluation FROM experiences WHERE id=? AND status='completed'",(experience_id,)).fetchone()
  if not r: raise EgoError('completed experience required')
  sid=new_id('RS')
  with self.db:
   self.db.execute('INSERT INTO reflection_strategies VALUES(?,?,?,?,?,?)',(sid,task_key,experience_id,strategy,dumps([experience_id]),now()))
   self.c.audit('reflection_strategy_saved',[sid,experience_id])
  return sid
 def retry_context(self,task_key,limit=3):
  rows=self.db.execute('SELECT * FROM reflection_strategies WHERE task_key=? ORDER BY created_at DESC LIMIT ?',(task_key,limit)).fetchall()
  return [{'strategy_id':r['id'],'experience_id':r['experience_id'],'strategy':r['strategy'],'created_at':r['created_at']} for r in rows]

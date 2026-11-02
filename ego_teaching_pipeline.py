#!/usr/bin/env python3
"""Compatibility intake: archive owner text only as unadopted external experience."""
import argparse,hashlib,json,sqlite3
from pathlib import Path
from ego_core import Ego
from ego_epistemic import EpistemicLoop
from ego_memory import save

def main():
 p=argparse.ArgumentParser(); p.add_argument('--root',default='.'); p.add_argument('--text',required=True); p.add_argument('--message-id',default=''); p.add_argument('--force',action='store_true'); a=p.parse_args()
 root=Path(a.root).resolve(); key=a.message_id or hashlib.sha256(a.text.encode()).hexdigest()
 with Ego(root) as core:
  core.db.execute("CREATE TABLE IF NOT EXISTS source_archive(message_id TEXT PRIMARY KEY,input_id TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
  previous=core.db.execute('SELECT input_id,status FROM source_archive WHERE message_id=?',(key,)).fetchone()
  if previous:
   print(json.dumps({'status':'duplicate','input_id':previous[0]},ensure_ascii=False)); return
  result=EpistemicLoop(core).intake('owner','owner-feishu',a.text.strip(),'飞书外部来源；仍需 EGO 自主判断',{'message_id':key})
  path=save('experience',f"主人经验来源 {result['input_id']}",a.text.strip(),'owner-feishu',tags=['external-experience','not-adopted','ego-a'])
  with core.db: core.db.execute('INSERT INTO source_archive VALUES(?,?,?,CURRENT_TIMESTAMP)',(key,result['input_id'],'received_not_adopted'))
  result['note_path']=path
  print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__': main()

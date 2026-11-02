#!/usr/bin/env python3
import argparse,json,sys
from ego_core import Ego,EgoError
from ego_memory_engine import MemoryEngine

def load(path):
 with open(path,encoding='utf-8') as f: return json.load(f)
def main():
 p=argparse.ArgumentParser(prog='ego-memory-engine'); p.add_argument('--root',default='.'); s=p.add_subparsers(dest='cmd',required=True)
 s.add_parser('sync')
 for name in ('search','consolidate','strategy','retry'):
  x=s.add_parser(name); x.add_argument('json_file')
 a=p.parse_args()
 try:
  with Ego(a.root) as c:
   e=MemoryEngine(c)
   if a.cmd=='sync': out=e.sync()
   else:
    d=load(a.json_file)
    if a.cmd=='search': out=e.search(d['query'],d.get('limit',8),d.get('entities'),d.get('after'),d.get('before'),d.get('kinds'))
    elif a.cmd=='consolidate': out=e.consolidate(d['label'],d['content'],d['evidence'],d.get('char_limit',2000))
    elif a.cmd=='strategy': out=e.record_strategy(d['task_key'],d['experience_id'],d['strategy'])
    else: out=e.retry_context(d['task_key'],d.get('limit',3))
   print(json.dumps(out,ensure_ascii=False,indent=2))
 except (EgoError,KeyError,json.JSONDecodeError) as ex: print(f'ERROR: {ex}',file=sys.stderr); sys.exit(2)
if __name__=='__main__': main()

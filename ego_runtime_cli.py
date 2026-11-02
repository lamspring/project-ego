"""Command interface for the persistent EGO execution runtime."""
import argparse,json,sys
from ego_core import Ego,EgoError,dumps
from ego_runtime import Runtime

def load(path):
 with open(path,encoding='utf-8') as f:return json.load(f)

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('command',choices=['ingest','route','claim','heartbeat','finish','intervene','inbox','recall','recall-trigger','watchdog','status']);p.add_argument('args',nargs='*');p.add_argument('--worker');p.add_argument('--work-id');p.add_argument('--lease',type=int,default=300);p.add_argument('--stale',type=int,default=600);a=p.parse_args()
 with Ego(a.root) as core:
  r=Runtime(core);cmd=a.command
  if cmd=='ingest':
   d=load(a.args[0]);out=r.ingest(d['source'],d['kind'],d['thread_id'],d['payload'],d.get('external_id'),d.get('occurred_at'))
  elif cmd=='route':
   d=load(a.args[1]);out=r.route(a.args[0],d['decision'],d['reason'],d.get('title'),d.get('brief'),d.get('priority',50))
  elif cmd=='claim':out=r.claim(a.worker,a.lease,a.work_id)
  elif cmd=='heartbeat':
   d=load(a.args[0]);out=r.heartbeat(d['work_id'],a.worker,d['revision'],d['progress'],a.lease)
  elif cmd=='finish':
   d=load(a.args[0]);out=r.finish(d['work_id'],a.worker,d['revision'],d['outcome'],d['result'])
  elif cmd=='intervene':
   d=load(a.args[1]);out=r.intervene(a.args[0],d['action'],d.get('actor','owner'),d.get('reason',''),d.get('brief'))
  elif cmd=='inbox':out=r.inbox(a.args[0],len(a.args)>1 and a.args[1]=='consume')
  elif cmd=='recall':out=r.recall(a.args[0])
  elif cmd=='recall-trigger':out=r.recall_trigger(a.args[0])
  elif cmd=='watchdog':out=r.watchdog(a.stale)
  else:out=r.status()
  print(dumps(out))
if __name__=='__main__':
 try:main()
 except EgoError as e:print(json.dumps({'error':str(e)},ensure_ascii=False));sys.exit(2)

#!/usr/bin/env python3
import argparse,json,sys
from ego_core import Ego,EgoError
from ego_learning import LearningEngine

def load(path):
 with open(path,encoding='utf-8') as f: return json.load(f)
def main():
 p=argparse.ArgumentParser(prog='ego-learning'); p.add_argument('--root',default='.'); s=p.add_subparsers(dest='cmd',required=True)
 s.add_parser('next')
 for name in ('propose','resolve','artifact','retrieve','iteration'):
  x=s.add_parser(name); x.add_argument('json_file')
 a=p.parse_args()
 try:
  with Ego(a.root) as c:
   e=LearningEngine(c)
   if a.cmd=='next': out=e.next_curriculum()
   else:
    d=load(a.json_file)
    if a.cmd=='propose': out=e.propose_curriculum(d['candidates'])
    elif a.cmd=='resolve': out=e.resolve_curriculum(d['id'],d['success'],d['result'])
    elif a.cmd=='artifact': out=e.register_artifact(d['skill_id'],d['description'],d['path'])
    elif a.cmd=='retrieve': out=e.retrieve_artifacts(d['query'],d.get('limit',5))
    else: out=e.record_iteration(d['skill_id'],d['artifact_id'],d['feedback'],d.get('reflection',''),d['passed'])
   print(json.dumps(out,ensure_ascii=False,indent=2))
 except (EgoError,KeyError,json.JSONDecodeError) as ex: print(f'ERROR: {ex}',file=sys.stderr); sys.exit(2)
if __name__=='__main__': main()

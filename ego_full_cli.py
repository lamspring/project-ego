#!/usr/bin/env python3
"""Advanced EGO operations. Complex arguments are JSON files to avoid shell quoting loss."""
import argparse,json,sys
from ego_core import Ego,EgoError
from ego_advanced import AdvancedEgo

def load(path):
 with open(path,encoding='utf-8') as f: return json.load(f)
def main():
 p=argparse.ArgumentParser(prog="ego-full"); p.add_argument('--root',default='.'); s=p.add_subparsers(dest='cmd',required=True)
 for name in ('growth-report','decay'): s.add_parser(name)
 for name in ('govern','counterfactual','appraise','entity','trust','skill-register','skill-test','identity','memory-index','shared'):
  x=s.add_parser(name); x.add_argument('json_file')
 a=p.parse_args()
 try:
  with Ego(a.root) as c:
   e=AdvancedEgo(c)
   if a.cmd=='growth-report': out=e.growth_report()
   elif a.cmd=='decay': out=e.decay_memories()
   else:
    d=load(a.json_file)
    if a.cmd=='govern': out=e.govern(d['candidates'],d.get('budget',1),d.get('context'))
    elif a.cmd=='counterfactual': out=e.counterfactual(d['experience_id'],d['interventions'])
    elif a.cmd=='appraise': out=e.appraise(d['experience_id'],d['state'],d['intensity'],d['source'],d.get('decay',.1))
    elif a.cmd=='entity': out=e.entity(d['name'],d.get('kind','person'),d.get('model'),d.get('evidence'))
    elif a.cmd=='trust': out=e.update_trust(d['entity_id'],d['experience_id'],d['delta'],d['condition'])
    elif a.cmd=='skill-register': out=e.register_skill(d['name'],d.get('conditions'))
    elif a.cmd=='skill-test': out=e.test_skill(d['skill_id'],d['passed'],d['score'],d['evidence'],d.get('notes',''))
    elif a.cmd=='identity': out=e.identity_event(d['kind'],d['before'],d['after'],d['reason'],d['evidence'])
    elif a.cmd=='memory-index': out=e.index_memory(d['experience_id'],d['summary'],d.get('salience',.5))
    elif a.cmd=='shared': out=e.receive_shared(d['source_id'],d['content'],d['provenance'],d['verification'])
   print(json.dumps(out,ensure_ascii=False,indent=2))
 except (EgoError,KeyError,json.JSONDecodeError) as ex: print(f'ERROR: {ex}',file=sys.stderr); sys.exit(2)
if __name__=='__main__': main()

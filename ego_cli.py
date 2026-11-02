#!/usr/bin/env python3
import argparse,json,sys
from ego_core import Ego,EgoError

def main():
 p=argparse.ArgumentParser(prog="ego",description="PROJECT EGO cognition core")
 p.add_argument("--root",default=".")
 s=p.add_subparsers(dest="cmd",required=True)
 s.add_parser("status"); s.add_parser("wake"); s.add_parser("recover"); s.add_parser("checkpoint"); s.add_parser("verify-audit")
 b=s.add_parser("begin"); b.add_argument("--context",required=True); b.add_argument("--self-state",default="unknown"); b.add_argument("--desired",required=True); b.add_argument("--expected",type=float,required=True); b.add_argument("--basis",required=True); b.add_argument("--source",default="real",choices=["real","simulation"])
 c=s.add_parser("complete"); c.add_argument("id"); c.add_argument("--action",required=True); c.add_argument("--summary",required=True); c.add_argument("--actual",type=float,required=True); c.add_argument("--dimensions",required=True,help="JSON object"); c.add_argument("--lessons",default="[]"); c.add_argument("--hypotheses",default="[]")
 r=s.add_parser("reflect"); r.add_argument("id"); r.add_argument("--facts",required=True); r.add_argument("--hypotheses",required=True); r.add_argument("--alternatives",required=True); r.add_argument("--adjustment",required=True)
 a=s.add_parser("belief-add"); a.add_argument("--statement",required=True); a.add_argument("--evidence",required=True); a.add_argument("--conditions",default="[]"); a.add_argument("--confidence",type=float,default=.5)
 a=s.add_parser("belief-revise"); a.add_argument("id"); a.add_argument("--decision",required=True); a.add_argument("--evidence",required=True); a.add_argument("--rationale",required=True)
 a=s.add_parser("goal-add"); a.add_argument("--description",required=True); a.add_argument("--formation",required=True); a.add_argument("--values",default="[]"); a.add_argument("--outcomes",default="[]"); a.add_argument("--approval",default="not_required"); a.add_argument("--origin",default="self")
 a=s.add_parser("goal-transition"); a.add_argument("id"); a.add_argument("--status",required=True); a.add_argument("--approved",action="store_true")
 a=s.add_parser("worldview-add"); a.add_argument("--worldview",required=True); a.add_argument("--reason",required=True); a.add_argument("--evidence",required=True)
 args=p.parse_args()
 try:
  with Ego(args.root) as e:
   if args.cmd=="status": out=e.status()
   elif args.cmd=="wake": out=e.wake()
   elif args.cmd=="recover": out=e.recover()
   elif args.cmd=="checkpoint": out=e.checkpoint()
   elif args.cmd=="verify-audit": out=e.verify_audit()
   elif args.cmd=="begin": out=e.begin(args.context,args.self_state,args.desired,args.expected,args.basis,source=args.source)
   elif args.cmd=="complete": out=e.complete(args.id,args.action,args.summary,args.actual,json.loads(args.dimensions),json.loads(args.hypotheses),json.loads(args.lessons))
   elif args.cmd=="reflect": out=e.reflect(args.id,json.loads(args.facts),json.loads(args.hypotheses),json.loads(args.alternatives),args.adjustment)
   elif args.cmd=="belief-add": out=e.add_belief(args.statement,json.loads(args.evidence),json.loads(args.conditions),args.confidence)
   elif args.cmd=="belief-revise": out=e.revise_belief(args.id,args.decision,args.evidence,args.rationale)
   elif args.cmd=="goal-add": out=e.propose_goal(args.description,json.loads(args.formation),json.loads(args.values),json.loads(args.outcomes),approval=args.approval,origin=args.origin)
   elif args.cmd=="goal-transition": out=e.transition_goal(args.id,args.status,args.approved)
   elif args.cmd=="worldview-add": out=e.evolve_worldview(json.loads(args.worldview),args.reason,json.loads(args.evidence))
   print(json.dumps(out,ensure_ascii=False,indent=2))
 except (EgoError,json.JSONDecodeError) as ex:
  print(f"ERROR: {ex}",file=sys.stderr); sys.exit(2)
if __name__=="__main__": main()

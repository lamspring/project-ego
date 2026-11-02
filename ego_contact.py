#!/usr/bin/env python3
"""Traceable owner-contact requests; channel delivery is separate from cognition."""
import argparse,json
from ego_core import Ego,new_id,now,dumps
SCHEMA="""CREATE TABLE IF NOT EXISTS contact_requests(id TEXT PRIMARY KEY,question TEXT NOT NULL,reason TEXT NOT NULL,evidence TEXT NOT NULL,status TEXT NOT NULL,channel TEXT NOT NULL,created_at TEXT NOT NULL,resolved_at TEXT);"""
def main():
 p=argparse.ArgumentParser(); p.add_argument('--root',default='.'); s=p.add_subparsers(dest='cmd',required=True)
 a=s.add_parser('ask'); a.add_argument('--question',required=True); a.add_argument('--reason',required=True); a.add_argument('--evidence',default='[]'); a.add_argument('--channel',default='feishu')
 s.add_parser('pending'); a=s.add_parser('resolve'); a.add_argument('id'); args=p.parse_args()
 with Ego(args.root) as e:
  e.db.executescript(SCHEMA)
  if args.cmd=='ask':
   cid=new_id('Q')
   with e.db:
    e.db.execute("INSERT INTO contact_requests VALUES(?,?,?,?, 'pending',?,?,NULL)",(cid,args.question,args.reason,dumps(json.loads(args.evidence)),args.channel,now())); e.audit('owner_guidance_requested',json.loads(args.evidence),permission='pending external delivery')
   out={'id':cid,'status':'pending','channel':args.channel,'note':'queued; no delivery claimed until channel confirms'}
  elif args.cmd=='pending': out=[dict(r) for r in e.db.execute("SELECT * FROM contact_requests WHERE status='pending'")]
  else:
   with e.db: e.db.execute("UPDATE contact_requests SET status='resolved',resolved_at=? WHERE id=?",(now(),args.id)); e.audit('owner_guidance_received',[args.id])
   out=args.id
  print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()

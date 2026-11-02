#!/usr/bin/env python3
"""Obsidian long-term knowledge layer using the official CLI, never direct Vault writes."""
import argparse,datetime as dt,json,subprocess,uuid
from ego_host import executable,setting
CLI=executable('obsidian','OBSIDIAN_CLI'); VAULT=setting('EGO_OBSIDIAN_VAULT','ego-a数据库')
FOLDERS={"teaching":"01-Teachings","experience":"01-Teachings","concept":"02-Concepts","relationship":"03-Relationships","reflection":"04-Reflections","judgment":"04-Reflections","growth":"05-Growth","inbox":"06-Inbox"}
def call(*args):
 p=subprocess.run([CLI,f"vault={VAULT}",*args],capture_output=True,text=True,encoding='utf-8',timeout=30)
 if p.returncode: raise RuntimeError(p.stderr.strip() or p.stdout.strip())
 return p.stdout.strip()
def slug(text): return ''.join(c if c.isalnum() else '-' for c in text).strip('-')[:48] or 'note'
def save(kind,title,content,source="owner",links=None,tags=None):
 folder=FOLDERS[kind]; stamp=dt.datetime.now().strftime('%Y%m%d-%H%M%S'); path=f"{folder}/{stamp}-{slug(title)}.md"
 linked='\n'.join(f"- [[{x}]]" for x in (links or [])); tagline=' '.join('#'+x for x in (tags or [kind,'ego-a']))
 body=f"---\ntype: {kind}\nsource: {source}\ncreated: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}\n---\n# {title}\n\n{content}\n\n{tagline}\n\n## 关联\n{linked}\n"
 call('create',f'path={path}',f'content={body}')
 # Independent read-back is mandatory.
 read=call('read',f'path={path}')
 if title not in read or content not in read: raise RuntimeError('Obsidian read-back mismatch')
 return path
def search(query,limit=10): return call('search',f'query={query}',f'limit={limit}')
def main():
 p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True)
 a=s.add_parser('save'); a.add_argument('kind',choices=FOLDERS); a.add_argument('--title',required=True); a.add_argument('--content',required=True); a.add_argument('--source',default='owner'); a.add_argument('--links',default='[]')
 a=s.add_parser('search'); a.add_argument('query'); a.add_argument('--limit',default=10,type=int)
 a=p.parse_args()
 if a.cmd=='save': out=save(a.kind,a.title,a.content,a.source,json.loads(a.links))
 else: out=search(a.query,a.limit)
 print(out)
if __name__=='__main__': main()

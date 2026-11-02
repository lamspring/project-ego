#!/usr/bin/env python3
"""Autonomous judgment CLI; JSON files prevent loss of reasoning structure."""
import argparse,json,sys
from ego_core import Ego,EgoError
from ego_epistemic import EpistemicLoop
from ego_memory import save

def load(path):
 with open(path,encoding='utf-8') as f: return json.load(f)
def note_source(d,data):
 return f"来源类型：{data['source_kind']}\n来源标识：{data['source_id']}\n上下文：{data['context']}\n\n## 原始内容\n{data['content']}\n\n## 来源评估\n{json.dumps(data.get('source_assessment',{}),ensure_ascii=False,indent=2)}\n\n> 仅作为外部经验来源，未自动采纳为信念、偏好或价值判断。"
def note_judgment(d,status):
 return f"输入：{d['input_id']}\n状态：{status}\n\n## 已知事实\n{json.dumps(d['facts'],ensure_ascii=False,indent=2)}\n\n## 假设\n{json.dumps(d['hypotheses'],ensure_ascii=False,indent=2)}\n\n## 替代解释\n{json.dumps(d['alternatives'],ensure_ascii=False,indent=2)}\n\n## 暂时结论\n{d['conclusion']}\n\n置信度：{d['confidence']}\n适用条件：{json.dumps(d['conditions'],ensure_ascii=False)}\n信息缺口：{json.dumps(d.get('gaps',[]),ensure_ascii=False)}\n可回滚行动：{d.get('reversible_action','')}\n\n> 这是 EGO 的暂时判断，不是客观事实，也不自动修改总体价值判断。"
def main():
 p=argparse.ArgumentParser(prog='ego-epistemic'); p.add_argument('--root',default='.'); p.add_argument('--no-obsidian',action='store_true'); s=p.add_subparsers(dest='cmd',required=True)
 for name in ('intake','judge','ask','answer'):
  x=s.add_parser(name); x.add_argument('json_file')
 x=s.add_parser('trace'); x.add_argument('input_id'); a=p.parse_args()
 try:
  with Ego(a.root) as c:
   loop=EpistemicLoop(c)
   if a.cmd=='trace': out=loop.trace(a.input_id)
   else:
    d=load(a.json_file)
    if a.cmd=='intake':
     out=loop.intake(d['source_kind'],d['source_id'],d['content'],d['context'],d.get('provenance'),d.get('source_assessment'),d.get('parent_input_id'),d.get('gap_id'))
     if not a.no_obsidian: out['note_path']=save('experience',f"外部经验 {out['input_id']}",note_source(d,d),d['source_kind'],tags=['external-experience','not-adopted','ego-a'])
    elif a.cmd=='judge':
     out=loop.judge(d['input_id'],d['facts'],d['hypotheses'],d['alternatives'],d['conclusion'],d['confidence'],d['conditions'],d.get('gaps'),d.get('reversible_action',''),d.get('prior_input_ids'))
     if not a.no_obsidian: out['note_path']=save('judgment',f"自主判断 {out['judgment_id']}",note_judgment(d,out['status']),'ego-a',tags=['judgment','provisional','ego-a'])
    elif a.cmd=='ask': out=loop.request_help(d['judgment_id'],d['question'],d['reason'],d.get('route','owner'))
    else:
     out=loop.intake('owner',d.get('source_id','owner-feishu'),d['content'],d['context'],d.get('provenance'),d.get('source_assessment'),d.get('parent_input_id'),d['gap_id'])
     out['requires_rejudgment']=True
     if not a.no_obsidian:
      source_note={**d,'source_kind':'owner','source_id':d.get('source_id','owner-feishu')}
      out['note_path']=save('experience',f"求助回答 {out['input_id']}",note_source(source_note,source_note),'owner',tags=['help-answer','requires-rejudgment','ego-a'])
   print(json.dumps(out,ensure_ascii=False,indent=2))
 except (EgoError,KeyError,json.JSONDecodeError) as ex: print(f'ERROR: {ex}',file=sys.stderr); sys.exit(2)
if __name__=='__main__': main()

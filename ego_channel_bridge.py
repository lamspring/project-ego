"""Normalize OpenClaw channel events into EGO's durable Trigger/Thread model."""
import argparse,json,sys
from ego_core import Ego,EgoError,dumps
from ego_runtime import Runtime

def normalize(event,context):
 if context.get('agentId')!='ego-a' or context.get('channelId')!='feishu':
  raise EgoError('event is outside the EGO-A Feishu binding')
 text=event.get('content','').strip()
 if not text:raise EgoError('empty channel content')
 message_id=str(event.get('messageId') or context.get('messageId') or '').strip()
 if not message_id:raise EgoError('channel message id required')
 thread=str(event.get('threadId') or event.get('replyToId') or context.get('sessionKey') or event.get('senderId') or '').strip()
 if not thread:raise EgoError('stable thread identity required')
 return {'source':'feishu','kind':'message','thread_id':f'feishu:{thread}','external_id':message_id,'payload':{'text':text,'sender_id':event.get('senderId') or context.get('senderId'),'reply_to_id':event.get('replyToId') or context.get('replyToId'),'session_key':context.get('sessionKey'),'media_pending':bool(event.get('mediaStagingPending'))}}

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args()
 data=json.load(sys.stdin)
 with Ego(a.root) as core:
  normalized=normalize(data['event'],data['context'])
  trigger_id=Runtime(core).ingest(normalized['source'],normalized['kind'],normalized['thread_id'],normalized['payload'],normalized['external_id'])
  print(dumps({'trigger_id':trigger_id,'thread_id':normalized['thread_id']}))
if __name__=='__main__':
 try:main()
 except (EgoError,KeyError,json.JSONDecodeError) as e:print(dumps({'error':str(e)}));sys.exit(2)

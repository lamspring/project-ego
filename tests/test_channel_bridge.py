import unittest
from ego_channel_bridge import normalize
from ego_core import EgoError

class ChannelBridgeTests(unittest.TestCase):
 def setUp(self):
  self.event={'content':'  继续上一个任务  ','messageId':'om_1','senderId':'ou_owner','threadId':'chat_1','replyToId':'om_0','mediaStagingPending':True}
  self.context={'agentId':'ego-a','channelId':'feishu','sessionKey':'agent:ego-a:feishu:chat_1'}
 def test_normalizes_stable_deduplicated_thread(self):
  n=normalize(self.event,self.context)
  self.assertEqual('feishu:chat_1',n['thread_id']);self.assertEqual('om_1',n['external_id']);self.assertEqual('继续上一个任务',n['payload']['text']);self.assertTrue(n['payload']['media_pending'])
 def test_scope_and_identity_required(self):
  with self.assertRaises(EgoError):normalize(self.event,{**self.context,'agentId':'main'})
  with self.assertRaises(EgoError):normalize({**self.event,'content':' '},self.context)
  with self.assertRaises(EgoError):normalize({**self.event,'messageId':''},self.context)

if __name__=='__main__':unittest.main()

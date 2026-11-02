import tempfile,threading,time,unittest
from ego_core import Ego,EgoError
from ego_runtime import Runtime

class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.core=Ego(self.tmp.name);self.r=Runtime(self.core)
 def tearDown(self):self.core.close();self.tmp.cleanup()
 def trigger(self,thread='thread:one',external=None):
  return self.r.ingest('feishu','message',thread,{'text':'调查问题'},external)
 def work(self,thread='thread:one'):
  t=self.trigger(thread);return self.r.route(t,'new','需要独立调查','调查问题','复现并记录证据')['work_id']
 def test_event_route_and_chain_recall(self):
  t=self.trigger();w=self.r.route(t,'new','需要处理','调查','保留证据')['work_id']
  direct=self.trigger();self.r.route(direct,'direct','已有同一任务')
  recalled=self.r.recall(w)
  self.assertEqual(2,len(recalled['triggers']));self.assertEqual('execution_only',recalled['context_scope']);self.assertEqual(1,len(self.r.inbox(w)))
  self.assertTrue(self.core.verify_audit())
 def test_duplicate_and_invalid_direct_rejected(self):
  self.trigger(external='message-1')
  with self.assertRaises(EgoError):self.trigger(external='message-1')
  t=self.trigger()
  with self.assertRaises(EgoError):self.r.route(t,'direct','无订阅不能直通')
 def test_ignore_does_not_create_work(self):
  t=self.trigger();self.r.route(t,'ignore','与 EGO 无关')
  self.assertEqual({},self.r.status()['work_items'])
 def test_only_one_parallel_claim_wins(self):
  w=self.work();results=[];errors=[]
  def claim(n):
   try:
    with Ego(self.tmp.name) as c:results.append(Runtime(c).claim(f'worker-{n}'))
   except Exception as e:errors.append(e)
  threads=[threading.Thread(target=claim,args=(i,)) for i in range(6)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual([],errors);self.assertEqual(1,sum(x is not None for x in results));self.assertEqual(5,sum(x is None for x in results))
 def test_worker_finish_and_subscription_cleanup(self):
  w=self.work();claimed=self.r.claim('worker-a')
  out=self.r.finish(w,'worker-a',claimed['revision'],'succeeded',{'summary':'已复现并验证'})
  self.assertEqual('succeeded',out['state'])
  t=self.trigger()
  with self.assertRaises(EgoError):self.r.route(t,'direct','任务已结束')
 def test_redirect_invalidates_old_worker(self):
  w=self.work();c=self.r.claim('worker-a');self.r.intervene(w,'redirect',reason='目标已改变',brief='只保留最小复现')
  with self.assertRaises(EgoError):self.r.finish(w,'worker-a',c['revision'],'succeeded',{'summary':'过期结果'})
  new=self.r.claim('worker-b');self.assertGreater(new['revision'],c['revision']);self.assertEqual('只保留最小复现',new['brief'])
 def test_cancel_and_resume_lifecycle(self):
  w=self.work();self.r.claim('worker-a');self.r.intervene(w,'pause',reason='等待外部信息')
  self.r.intervene(w,'resume',reason='信息已到位');self.r.claim('worker-b')
  self.r.intervene(w,'cancel',reason='主人停止')
  self.assertEqual('cancelled',self.r.recall(w)['work']['state'])
 def test_stale_worker_cannot_write_after_watchdog_requeue(self):
  w=self.work();c=self.r.claim('worker-a',lease_seconds=30)
  with self.core.db:self.core.db.execute("UPDATE work_items SET lease_until=? WHERE id=?",('2000-01-01T00:00:00+08:00',w))
  observations=self.r.watchdog();self.assertEqual('requeue',observations[0]['action'])
  with self.assertRaises(EgoError):self.r.finish(w,'worker-a',c['revision'],'failed',{'summary':'旧 worker 失败'})
  self.assertIsNotNone(self.r.claim('worker-b'))
 def test_no_progress_is_observed_without_fabricating_failure(self):
  w=self.work();self.r.claim('worker-a')
  with self.core.db:self.core.db.execute("UPDATE work_items SET last_progress=? WHERE id=?",('2000-01-01T00:00:00+08:00',w))
  obs=self.r.watchdog(stale_seconds=60);self.assertEqual('observe',obs[0]['action']);self.assertEqual('no_progress',obs[0]['kind'])
 def test_direct_inbox_consumed_once(self):
  w=self.work();t=self.trigger();self.r.route(t,'direct','同一线程')
  self.assertEqual(1,len(self.r.inbox(w,True)));self.assertEqual([],self.r.inbox(w,True))
 def test_many_to_many_subscription_and_new_topic_same_dm(self):
  first=self.work();second=self.work()
  t=self.trigger();r=self.r.route(t,'direct','同一事件流与两个任务都相关')
  self.assertEqual({first,second},set(r['work_ids']))
  self.assertEqual(1,len(self.r.inbox(first)));self.assertEqual(1,len(self.r.inbox(second)))
 def test_targeted_claim_and_inline_spill(self):
  first=self.work();second=self.work();claimed=self.r.claim('worker-b',work_id=second)
  self.assertEqual(second,claimed['work_id']);self.assertIsNone(self.r.claim('worker-b',work_id=second))
  long=self.r.ingest('feishu','message','thread:one',{'text':'x'*700})
  recalled=self.r.recall(first);payload=[t for t in recalled['triggers'] if t['id']==long][0]['payload']
  self.assertEqual(200,payload['spilled_chars']);self.assertEqual(700,len(self.r.recall_trigger(long)['payload']['text']))

if __name__=='__main__':unittest.main()

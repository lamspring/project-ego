import tempfile,unittest
from ego_core import Ego,EgoError
from ego_epistemic import EpistemicLoop

class EpistemicTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.c=Ego(self.t.name); self.e=EpistemicLoop(self.c)
  self.src=self.e.intake('owner','owner','旧经验与新信息冲突','测试情境')['input_id']
 def tearDown(self): self.c.close(); self.t.cleanup()
 def counts(self):
  return tuple(self.c.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('beliefs','preferences','worldview_versions'))
 def test_intake_never_adopts_owner_claim(self):
  r=self.c.db.execute('SELECT status FROM external_inputs WHERE id=?',(self.src,)).fetchone()
  self.assertEqual(r['status'],'received_not_adopted'); self.assertEqual(self.counts(),(0,0,0))
 def test_judgment_preserves_alternatives_and_conditions(self):
  j=self.e.judge(self.src,['新信息与旧经验不同'],['适用条件可能不同'],['旧经验错误','新信息错误'],'暂按条件区分',.4,['仅限测试情境'])
  self.assertEqual(j['status'],'provisional'); self.assertFalse(j['cognitive_state_changed']); self.assertEqual(self.counts(),(0,0,0))
 def test_gap_answer_requires_new_independent_judgment(self):
  j=self.e.judge(self.src,['只有单方描述'],['可能缺少背景'],['双方均可能不完整'],'无法判断',.2,['需更多信息'],['缺少可验证背景'])
  gap=self.e.request_help(j['judgment_id'],'当时有哪些可观察事实？','缺少判断依据')['gap_id']
  answer=self.e.intake('owner','owner','补充背景','回答求教',gap_id=gap)
  self.assertTrue(answer['requires_judgment'])
  self.assertEqual(self.c.db.execute('SELECT status FROM knowledge_gaps WHERE id=?',(gap,)).fetchone()[0],'answered_requires_rejudgment')
  self.assertEqual(self.counts(),(0,0,0))
 def test_help_cannot_be_requested_without_gap(self):
  j=self.e.judge(self.src,['事实'],['假设'],['替代'],'暂定',.5,['条件'])
  with self.assertRaises(EgoError): self.e.request_help(j['judgment_id'],'问题','原因')
 def test_trace_contains_source_and_reasoning(self):
  j=self.e.judge(self.src,['事实'],['假设'],['替代'],'暂定',.5,['条件'])
  trace=self.e.trace(self.src)
  self.assertEqual(trace['judgments'][0]['id'],j['judgment_id'])

if __name__=='__main__': unittest.main()

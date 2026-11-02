import json,tempfile,unittest
from pathlib import Path
from ego_core import Ego,EgoError
from ego_advanced import AdvancedEgo
from ego_memory_engine import MemoryEngine
from ego_learning import LearningEngine

class MemoryLearningTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.c=Ego(self.t.name); self.a=AdvancedEgo(self.c); self.m=MemoryEngine(self.c); self.l=LearningEngine(self.c)
  self.x=self.c.begin('信息核对','ok','learn',.8,'fixture'); self.c.complete(self.x,'test','缺少字段',.2,{'task_completion':.2,'knowledge_growth':.7})
 def tearDown(self): self.c.close(); self.t.cleanup()
 def test_sync_is_idempotent_and_raw_experience_unchanged(self):
  self.assertEqual(self.m.sync()['new_items'],1); self.assertEqual(self.m.sync()['new_items'],0)
  self.assertIsNotNone(self.c.db.execute('SELECT 1 FROM experiences WHERE id=?',(self.x,)).fetchone())
 def test_retrieval_exposes_three_signals_and_vector_limit(self):
  self.m.sync(); r=self.m.search('信息核对')[0]
  self.assertEqual(r['vector_model'],'hashed-ngram-v1'); self.assertIn('recency',r['signals']); self.assertIn('importance',r['signals'])
 def test_consolidation_preserves_versions_and_requires_evidence(self):
  self.m.sync(); v1=self.m.consolidate('合作经验','先检查必需字段',[self.x]); v2=self.m.consolidate('合作经验','先检查字段，再决定行动',[self.x])
  self.assertEqual(v2['version'],2); self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM memory_block_versions').fetchone()[0],2)
  with self.assertRaises(EgoError): self.m.consolidate('空','无证据',[])
 def test_reflexion_strategy_is_injected_into_next_retry_context(self):
  self.m.record_strategy('字段核对',self.x,'下一次先运行字段完整性检查')
  self.assertIn('完整性检查',self.m.retry_context('字段核对')[0]['strategy'])
 def test_curriculum_tracks_failure_without_execution(self):
  ids=self.l.propose_curriculum([{'task':'学习字段校验','rationale':'既有失败显示缺口','state_evidence':[self.x],'novelty':.6,'feasibility':.9}])
  self.assertEqual(self.l.next_curriculum()['execution'],'requires separate action lifecycle')
  self.assertEqual(self.l.resolve_curriculum(ids[0],False,'测试未通过'),'failed')
 def test_skill_artifact_is_real_file_and_versioned(self):
  s=self.a.register_skill('字段校验'); Path(self.t.name,'check.py').write_text('print(1)',encoding='utf-8')
  a=self.l.register_artifact(s,'检查输入字段','check.py')
  self.assertEqual(a['status'],'learning'); self.assertEqual(a['version'],1)
 def test_failed_skill_iteration_requires_feedback_for_retry(self):
  s=self.a.register_skill('字段校验'); Path(self.t.name,'check.py').write_text('print(1)',encoding='utf-8'); a=self.l.register_artifact(s,'检查输入字段','check.py')
  r=self.l.record_iteration(s,a['artifact_id'],'缺少边界测试','补充空字段测试',False)
  self.assertIn('空字段',r['next_attempt_must_include'])

if __name__=='__main__': unittest.main()

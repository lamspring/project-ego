import tempfile,unittest
from ego_core import Ego,EgoError
from ego_advanced import AdvancedEgo

class AdvancedTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.c=Ego(self.t.name); self.a=AdvancedEgo(self.c)
  self.x=self.c.begin("cooperation","ok","learn",.8,"fixture",source="simulation")
  self.c.complete(self.x,"test","information absent",.2,{"task_completion":.2,"knowledge_growth":.6})
 def tearDown(self): self.c.close(); self.t.cleanup()
 def test_appraisal_is_persistent_not_performance_claim(self):
  aid=self.a.appraise(self.x,"uncertainty",.8,"prediction error")
  self.assertEqual(self.c.db.execute("SELECT state FROM appraisals WHERE id=?",(aid,)).fetchone()[0],"uncertainty")
 def test_counterfactual_remains_unverified(self):
  r=self.a.counterfactual(self.x,["verify information first"])
  self.assertEqual(r['analysis'][0]['predicted_effect'],"unverified")
 def test_relationship_evidence_and_no_global_transfer(self):
  ent=self.a.entity("fixture partner"); self.a.update_trust(ent,self.x,-.2,"information missing in this task")
  r=self.c.db.execute("SELECT trust,conditions FROM relationships WHERE entity_id=?",(ent,)).fetchone()
  self.assertAlmostEqual(r['trust'],.3); self.assertIn("no automatic transfer",r['conditions'])
 def test_skill_requires_two_passing_tests(self):
  s=self.a.register_skill("verify inputs"); self.a.test_skill(s,True,.8,[self.x]); r=self.a.test_skill(s,True,.9,[self.x])
  self.assertEqual(r['status'],"validated")
 def test_identity_requires_evidence(self):
  with self.assertRaises(EgoError): self.a.identity_event("value_change",{},{},"no evidence",[])
 def test_memory_decay_never_deletes_raw_experience(self):
  self.a.index_memory(self.x,"summary",.4); self.a.decay_memories(0)
  self.assertIsNotNone(self.c.db.execute("SELECT 1 FROM experiences WHERE id=?",(self.x,)).fetchone())
 def test_external_knowledge_does_not_become_value(self):
  x=self.a.receive_shared("book","claim",{"author":"fixture"},{"status":"verified"})
  self.assertEqual(self.c.db.execute("SELECT status FROM shared_experiences WHERE id=?",(x,)).fetchone()[0],"knowledge_not_value")
 def test_governance_rest_when_only_approval_action(self):
  r=self.a.govern([{"action":"publish","goal_relevance":1,"cost":0,"requires_approval":True}])
  self.assertEqual(r['chosen'],"rest")
 def test_governance_selects_local_positive_action(self):
  r=self.a.govern([{"action":"research","goal_relevance":.9,"information_gain":.8,"cost":.2,"risk":.1}])
  self.assertEqual(r['chosen'],"research")
 def test_growth_report_includes_null_and_audit(self):
  r=self.a.growth_report(); self.assertTrue(r['audit_valid']); self.assertIn("negative_or_null_observations",r)

if __name__=='__main__': unittest.main()

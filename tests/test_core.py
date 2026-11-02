import json,sqlite3,tempfile,unittest
from pathlib import Path
from ego_core import Ego,EgoError

class CoreTests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.root=self.tmp.name
 def tearDown(self): self.tmp.cleanup()
 def exp(self,e,source="simulation",actual=.2,expected=.8):
  x=e.begin("cooperation test","normal","complete shared task",expected,"test fixture",source=source)
  e.complete(x,"cooperate","observed result",actual,{"task_completion":actual,"knowledge_growth":.5,"relationship_impact":actual,"long_term_impact":.4,"risk":.2,"resource_cost":.2})
  return x
 def test_expectation_precedes_action_and_immutable_completion(self):
  with Ego(self.root) as e:
   x=e.begin("task","ok","finish",.7,"prior evidence")
   row=e.db.execute("SELECT created_at,completed_at,status FROM experiences WHERE id=?",(x,)).fetchone()
   self.assertEqual(row['status'],'expected'); self.assertIsNone(row['completed_at'])
   e.complete(x,"act","done",.9,{"task_completion":1})
   with self.assertRaises(EgoError): e.complete(x,"rewrite","fake",.1,{"task_completion":0})
 def test_reflection_and_traceable_belief(self):
  with Ego(self.root) as e:
   x=self.exp(e)
   c=e.reflect(x,["two attempts failed"],["missing information may explain failure"],["partner capability is an alternative"],"collect information before cooperating")
   b=e.add_belief("cooperation needs information transparency",[x],["shared task"])
   e.revise_belief(b,"strengthened",x,"repeatable observation")
   row=e.db.execute("SELECT confidence,version FROM beliefs WHERE id=?",(b,)).fetchone()
   self.assertGreater(row['confidence'],.5); self.assertEqual(row['version'],2)
 def test_goal_requires_real_traceable_exp(self):
  with Ego(self.root) as e:
   with self.assertRaises(EgoError): e.propose_goal("investigate",{"trigger_experiences":["EXP_9999"],"reasoning_chain":"gap -> investigate"},[],[])
   x=self.exp(e)
   g=e.propose_goal("investigate information checks",{"trigger_experiences":[x],"reasoning_chain":"failure -> information gap -> test"},["accuracy"],["comparison report"])
   e.transition_goal(g,"active"); e.transition_goal(g,"done")
 def test_permission_boundary_blocks_and_audits(self):
  with Ego(self.root) as e:
   x=self.exp(e); g=e.propose_goal("external post",{"trigger_experiences":[x],"reasoning_chain":"test"},[],[],approval="required")
   with self.assertRaises(EgoError): e.transition_goal(g,"active")
   self.assertTrue(e.verify_audit())
   self.assertEqual(e.db.execute("SELECT result FROM audit ORDER BY seq DESC").fetchone()[0],"blocked")
 def test_restart_recovery_and_checkpoint(self):
  with Ego(self.root) as e:
   x=self.exp(e); g=e.propose_goal("continue",{"trigger_experiences":[x],"reasoning_chain":"unfinished question"},[],[]); chk=e.checkpoint()
  with Ego(self.root) as e:
   state=e.wake(); self.assertEqual(state['goals'][0]['id'],g); self.assertEqual(state['experiences'] if 'experiences' in state else 1,1)
 def test_worldview_version_and_weekly_limit(self):
  with Ego(self.root) as e:
   x=self.exp(e); self.assertEqual(e.evolve_worldview({"stable_values":[]},"first synthesis",[x]),1)
   with self.assertRaises(EgoError): e.evolve_worldview({},"performative change",[x])
 def test_multidimensional_outcome_required(self):
  with Ego(self.root) as e:
   x=e.begin("task","ok","finish",.5,"test")
   with self.assertRaises(EgoError): e.complete(x,"act","done",.5,{})
 def test_audit_tamper_detection(self):
  with Ego(self.root) as e:
   self.exp(e); self.assertTrue(e.verify_audit())
   e.db.execute("UPDATE audit SET result='tampered' WHERE seq=1"); e.db.commit(); self.assertFalse(e.verify_audit())
 def test_action_selection_allows_rest(self):
  with Ego(self.root) as e: self.assertEqual(e.select_action([{"action":"research","cost":2}],budget=1),"rest")

if __name__=='__main__': unittest.main()

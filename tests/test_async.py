import sys,tempfile,time,unittest
from ego_core import Ego
from ego_async import AsyncJobs

class AsyncTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.core=Ego(self.tmp.name);self.jobs=AsyncJobs(self.core)
 def tearDown(self):self.core.close();self.tmp.cleanup()
 def wait(self,job):
  for _ in range(100):
   out=self.jobs.poll(job)
   if out['state']!='running':time.sleep(.15);return out
   time.sleep(.05)
  self.fail('async job did not finish')
 def test_start_returns_before_result_and_persists_success(self):
  job=self.jobs.start([sys.executable,'-c','import time;time.sleep(.3);print("done")'])
  self.assertEqual('running',job['state']);out=self.wait(job['job_id'])
  self.assertEqual('succeeded',out['state']);self.assertEqual(0,out['exit_code'])
  self.assertIn('done',self.jobs.output(job['job_id'])['output'])
 def test_nonzero_exit_is_failure_not_success(self):
  job=self.jobs.start([sys.executable,'-c','raise SystemExit(7)']);out=self.wait(job['job_id'])
  self.assertEqual('failed',out['state']);self.assertEqual(7,out['exit_code'])

if __name__=='__main__':unittest.main()

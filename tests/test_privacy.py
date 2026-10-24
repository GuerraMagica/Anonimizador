import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

class PrivacyTests(unittest.TestCase):
    def test_fresh_process_real_model_end_to_end_without_network(self):
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('privacy_probe.py'))],
                              env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=60)
        self.assertNotIn('sentinelprivacy47@example.com',result.stdout+result.stderr)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout);self.assertEqual(data['network_attempts'],0)
        self.assertTrue(data['original_preserved']);self.assertTrue(data['no_private_artifacts'])

if __name__=='__main__':unittest.main()

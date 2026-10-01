import json
import platform
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from emergence.executor import capability, run_python


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_unsupported_platform_never_launches_code(self):
        with patch('emergence.executor.capability',return_value={'available':False,'backend':'unavailable','details':'unsupported'}), patch('subprocess.Popen') as popen:
            receipt=run_python(self.root/'trial','raise Exception("must not run")')
        self.assertEqual(receipt['status'],'unavailable')
        popen.assert_not_called()

    @unittest.skipUnless(platform.system()=='Darwin','macOS sandbox integration')
    def test_isolation_and_environment(self):
        self.assertTrue(capability()['available'],capability())
        sentinel=self.root/'private.txt';sentinel.write_text('do not expose')
        code="""import os,json,pathlib,socket,subprocess
blocked=[]
for operation in (
    lambda: pathlib.Path(SENTINEL).read_text(),
    lambda: pathlib.Path(SENTINEL).write_text('changed'),
    lambda: socket.socket().connect(('127.0.0.1',9)),
    lambda: subprocess.run(['/usr/bin/true']),
    lambda: os.fork()):
    try: operation()
    except PermissionError: blocked.append(True)
    except OSError: blocked.append(False)
    else: blocked.append(False)
pathlib.Path('allowed.txt').write_text('workspace')
print(json.dumps({'blocked':blocked,'secret_visible':'LAB_TEST_SECRET' in os.environ}))
""".replace('SENTINEL',repr(str(sentinel)))
        with patch.dict('os.environ',{'LAB_TEST_SECRET':'private-test-value'}):
            receipt=run_python(self.root/'trial',code)
        self.assertEqual(receipt['status'],'passed',receipt)
        self.assertEqual(receipt['data'],{'blocked':[True]*5,'secret_visible':False})
        self.assertEqual(sentinel.read_text(),'do not expose')

    @unittest.skipUnless(platform.system()=='Darwin','macOS sandbox integration')
    def test_timeout_and_fast_workspace_quota(self):
        receipt=run_python(self.root/'timeout','while True: pass',timeout=.5)
        self.assertEqual(receipt['status'],'timeout')
        receipt=run_python(self.root/'quota','from pathlib import Path\nfor i in range(140):Path(str(i)).touch()\nprint("{}")')
        self.assertEqual(receipt['status'],'output_limit')

    @unittest.skipUnless(platform.system()=='Darwin','macOS sandbox integration')
    def test_nested_invalid_json_retains_receipt(self):
        receipt=run_python(self.root/'invalid','print("["*2000+"0"+"]"*2000)')
        self.assertEqual(receipt['status'],'invalid_output')
        self.assertEqual(receipt['exit_code'],0)


if __name__=='__main__':unittest.main()

"""Trusted process restart and pre-publication death, never hostile isolation."""
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import unittest

from nomad.persistent import PersistentController, read_checkpoint, write_checkpoint
from nomad.supervised import run_supervised

ROOT=Path(__file__).resolve().parents[1]


class PersistentProcessTests(unittest.TestCase):
    def test_fresh_process_restores_same_native_future_forecasts(self):
        rng=random.Random(18186004)
        observations=[(rng.randrange(2),rng.randrange(2)) for _ in range(96)]
        model=PersistentController()
        for a,y in observations[:64]: model.predict(a); model.observe(a,y)
        with tempfile.TemporaryDirectory(prefix='nomad-state-process-') as temp:
            snapshot=Path(temp)/'state.json'; data=Path(temp)/'public.json'
            write_checkpoint(snapshot,model.snapshot()); data.write_text(json.dumps(observations[64:]))
            restored=PersistentController.load(read_checkpoint(snapshot))
            restored.decide(available_actions=('native',))
            expected=[]
            for a,y in observations[64:]: expected.append(restored.predict(a)); restored.observe(a,y)
            code=('import json,sys; from nomad.persistent import PersistentController,read_checkpoint; '
                  'm=PersistentController.load(read_checkpoint(sys.argv[1])); m.decide(available_actions=("native",)); out=[]; '
                  'exec("for a,y in json.load(open(sys.argv[2])):\\n out.append(m.predict(a)); m.observe(a,y)"); '
                  'print(json.dumps(out))')
            result=run_supervised([sys.executable,'-B','-c',code,str(snapshot),str(data)],cwd=ROOT,
                timeout_s=30,max_output_bytes=20000,windows_memory_mib=512,windows_max_processes=4)
            self.assertEqual(result.returncode,0,result.output.decode(errors='replace'))
            self.assertFalse(result.timed_out)
            self.assertEqual(json.loads(result.output),expected)

    def test_writer_process_death_before_replace_preserves_authoritative_state(self):
        model=PersistentController()
        with tempfile.TemporaryDirectory(prefix='nomad-state-death-') as temp:
            path=Path(temp)/'state.json'; write_checkpoint(path,model.snapshot())
            before=path.read_bytes()
            code=('import os,sys; from pathlib import Path; '
                  'from nomad.persistent import PersistentController,write_checkpoint; '
                  'm=PersistentController(); m.predict(0); m.observe(0,1); '
                  'os.replace=lambda *args: os._exit(7); write_checkpoint(Path(sys.argv[1]),m.snapshot())')
            result=run_supervised([sys.executable,'-B','-c',code,str(path)],cwd=ROOT,
                timeout_s=30,max_output_bytes=20000,windows_memory_mib=512,windows_max_processes=4)
            self.assertEqual(result.returncode,7)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(PersistentController.load(read_checkpoint(path)).history,[])
            self.assertTrue(list(Path(temp).glob('state.json.*.tmp')))


if __name__=='__main__': unittest.main()

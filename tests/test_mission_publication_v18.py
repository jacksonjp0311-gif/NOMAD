"""Bounded mission publication refusals and a controlled Windows sharing lock."""
import ctypes
import os
import stat
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from nomad import platform_mission as mission
from nomad.mission_runtime import MissionHold


def denied(code):
    error=PermissionError('controlled Windows rename refusal')
    error.winerror=code
    return error


class MissionPublicationTests(unittest.TestCase):
    def paths(self,base):
        stage=Path(base)/'stage';stage.mkdir();(stage/'evidence').write_bytes(b'owned evidence')
        return stage,Path(base)/'mission'

    def test_known_transient_windows_denials_retry_then_publish_once(self):
        for code in (5,32):
            with self.subTest(code=code),tempfile.TemporaryDirectory() as temporary:
                stage,root=self.paths(temporary);real=Path.rename;calls=[]
                def rename(source,destination):
                    calls.append((source,destination))
                    if len(calls)<3:raise denied(code)
                    return real(source,destination)
                with patch.object(mission.os,'name','nt'),patch.object(Path,'rename',rename),patch.object(mission.time,'sleep') as pause:
                    mission._publish_staged_mission(stage,root)
                self.assertEqual(len(calls),3);self.assertEqual(pause.call_count,2)
                self.assertEqual((root/'evidence').read_bytes(),b'owned evidence');self.assertFalse(stage.exists())

    def test_persistent_denial_has_finite_budget_and_no_published_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,root=self.paths(temporary)
            with patch.object(mission.os,'name','nt'),patch.object(Path,'rename',side_effect=denied(5)) as rename,patch.object(mission.time,'sleep') as pause:
                with self.assertRaisesRegex(MissionHold,'bounded retries'):mission._publish_staged_mission(stage,root)
            self.assertEqual(rename.call_count,6);self.assertEqual(pause.call_count,5)
            self.assertAlmostEqual(sum(call.args[0] for call in pause.call_args_list),1.55)
            self.assertFalse(root.exists());self.assertEqual((stage/'evidence').read_bytes(),b'owned evidence')

    def test_unknown_error_is_not_retried_or_suppressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,root=self.paths(temporary);error=denied(123)
            with patch.object(mission.os,'name','nt'),patch.object(Path,'rename',side_effect=error) as rename,patch.object(mission.time,'sleep') as pause:
                with self.assertRaises(PermissionError) as caught:mission._publish_staged_mission(stage,root)
            self.assertIs(caught.exception,error);rename.assert_called_once();pause.assert_not_called()
            self.assertTrue(stage.exists());self.assertFalse(root.exists())

    def test_existing_or_concurrently_appearing_destination_is_never_overwritten(self):
        for initially_exists in (True,False):
            with self.subTest(initially_exists=initially_exists),tempfile.TemporaryDirectory() as temporary:
                stage,root=self.paths(temporary)
                def appear(_delay):root.mkdir();(root/'foreign').write_bytes(b'preserve me')
                if initially_exists:appear(0)
                with patch.object(mission.os,'name','nt'),patch.object(Path,'rename',side_effect=denied(32)) as rename,patch.object(mission.time,'sleep',side_effect=appear):
                    with self.assertRaises(FileExistsError):mission._publish_staged_mission(stage,root)
                self.assertEqual(rename.call_count,0 if initially_exists else 1)
                self.assertEqual((root/'foreign').read_bytes(),b'preserve me')
                self.assertEqual((stage/'evidence').read_bytes(),b'owned evidence')

    def test_move_then_exception_is_held_without_guessing_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,root=self.paths(temporary);real=Path.rename
            def uncertain(source,destination):real(source,destination);raise denied(5)
            with patch.object(mission.os,'name','nt'),patch.object(Path,'rename',uncertain),patch.object(mission.time,'sleep') as pause:
                with self.assertRaisesRegex(MissionHold,'ambiguous'):mission._publish_staged_mission(stage,root)
            pause.assert_not_called();self.assertFalse(stage.exists())
            self.assertEqual((root/'evidence').read_bytes(),b'owned evidence')

    def test_dangling_destination_entry_is_not_treated_as_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,root=self.paths(temporary);real=Path.lstat
            self.assertFalse(root.exists())
            # An inert lstat double needs no Windows symlink privilege. The
            # target has no stat-able file but its link entry still conflicts.
            dangling=os.stat_result((stat.S_IFLNK|0o777,7,1,1,0,0,0,0,0,0))
            def metadata(path,*args,**kwargs):
                return dangling if path==root else real(path,*args,**kwargs)
            with patch.object(Path,'lstat',metadata),patch.object(Path,'rename') as rename:
                with self.assertRaises(FileExistsError):mission._publish_staged_mission(stage,root)
            rename.assert_not_called();self.assertTrue(stage.exists())

    def test_source_replacement_or_reparse_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,root=self.paths(temporary)
            def replace(_delay):
                stage.rename(stage.with_name('preserved-old-stage'))
                stage.mkdir();(stage/'foreign').write_bytes(b'other owner')
            real=Path.rename
            def rename(source,destination):
                if destination==root:raise denied(5)
                return real(source,destination)
            with patch.object(mission.os,'name','nt'),patch.object(Path,'rename',rename),patch.object(mission.time,'sleep',side_effect=replace):
                with self.assertRaisesRegex(MissionHold,'identity changed'):mission._publish_staged_mission(stage,root)
            self.assertFalse(root.exists());self.assertEqual((stage/'foreign').read_bytes(),b'other owner')
        with tempfile.TemporaryDirectory() as temporary:
            stage,root=self.paths(temporary)
            with patch.object(mission,'_reparse',return_value=True),patch.object(Path,'rename') as rename:
                with self.assertRaises(MissionHold):mission._publish_staged_mission(stage,root)
            rename.assert_not_called()

    @unittest.skipUnless(os.name=='nt','native Windows directory-sharing test')
    def test_native_windows_sharing_denial_recovers_after_handle_release(self):
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=(wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,
                                     wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE)
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=(wintypes.HANDLE,);kernel.CloseHandle.restype=wintypes.BOOL
        with tempfile.TemporaryDirectory() as temporary:
            stage,root=self.paths(temporary)
            handle=kernel.CreateFileW(str(stage),0x80000000,3,None,3,0x02000000,None)
            if handle==wintypes.HANDLE(-1).value:raise ctypes.WinError(ctypes.get_last_error())
            timer=None
            try:
                with self.assertRaises(PermissionError) as refusal:stage.rename(root)
                self.assertIn(refusal.exception.winerror,(5,32))
                timer=threading.Timer(0.12,lambda:kernel.CloseHandle(handle));timer.start()
                mission._publish_staged_mission(stage,root)
                timer.join();handle=None
                self.assertEqual((root/'evidence').read_bytes(),b'owned evidence')
            finally:
                if timer:timer.join();handle=None
                if handle is not None:kernel.CloseHandle(handle)


if __name__=='__main__':unittest.main()

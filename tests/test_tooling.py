"""Cross-platform setup, profile isolation, integrity, and process cleanup checks."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import setup as runtime_setup

# Avoid a collision with other installed modules named "run".
spec=importlib.util.spec_from_file_location('echo_run',ROOT/'tools/run.py')
launcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class PlatformTests(unittest.TestCase):
    def test_native_platforms_and_architectures(self):
        self.assertEqual(runtime_setup.platform_key('Windows','AMD64'),'windows')
        self.assertEqual(runtime_setup.platform_key('Linux','x86_64'),'linux')
        for system,machine in [('Windows','ARM64'),('Linux','aarch64'),('Darwin','arm64')]:
            with self.subTest(system=system,machine=machine),self.assertRaises(RuntimeError):
                runtime_setup.platform_key(system,machine)

    def test_windows_uses_exe_and_separate_runtime(self):
        self.assertEqual(runtime_setup.engine_binary('windows').name,'openmw.exe')
        self.assertEqual(runtime_setup.engine_binary('linux').name,'openmw.x86_64')
        self.assertNotEqual(runtime_setup.engine_directory('windows'),runtime_setup.engine_directory('linux'))


class IntegrityTests(unittest.TestCase):
    def test_cabinet_boundaries_exclude_signature_trailer(self):
        cabinet=bytearray(64)
        cabinet[:4]=b'MSCF'
        struct.pack_into('<I',cabinet,8,len(cabinet))
        struct.pack_into('<I',cabinet,16,36)
        cabinet[24:26]=bytes((3,1))
        data=b'bundle-prefix'+cabinet+b'authenticode-trailer'
        self.assertEqual(list(runtime_setup.cabinet_payloads(data)),[bytes(cabinet)])
        self.assertEqual(list(runtime_setup.cabinet_payloads(cabinet[:-1])),[])

    def test_corrupted_cached_download_is_rejected_without_execution_or_download(self):
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'engine.exe'
            archive.write_bytes(b'corrupted file')
            spec={'url':'https://example.invalid/unused','sha256':hashlib.sha256(b'official file').hexdigest()}
            with mock.patch.object(runtime_setup.urllib.request,'urlopen') as network:
                with self.assertRaisesRegex(RuntimeError,'Checksum mismatch'):
                    runtime_setup.download_checked(spec,archive)
                network.assert_not_called()
            self.assertEqual(archive.read_bytes(),b'corrupted file')

    def test_partial_unverified_download_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'engine.exe'
            response=mock.MagicMock()
            response.__enter__.return_value.read.side_effect=[b'wrong file',b'']
            spec={'url':'https://example.invalid/unused','sha256':'0'*64}
            with mock.patch.object(runtime_setup.urllib.request,'urlopen',return_value=response):
                with self.assertRaisesRegex(RuntimeError,'Checksum mismatch'):
                    runtime_setup.download_checked(spec,archive)
            self.assertFalse(archive.exists())
            self.assertFalse(archive.with_suffix('.exe.partial').exists())


class ProfileTests(unittest.TestCase):
    def test_unicode_and_spaces_use_utf8_and_do_not_load_morrowind(self):
        with tempfile.TemporaryDirectory() as directory:
            profile=Path(directory)/'Gra Łowca Echa z polskimi znakami'
            launcher.configure(profile,False)
            data=(profile/'openmw.cfg').read_bytes()
            self.assertFalse(data.startswith(b'\xef\xbb\xbf'))
            config=data.decode('utf-8')
            self.assertIn(profile.as_posix(),config)
            # Windows writes CRLF and Linux writes LF; both are valid config files.
            lines=config.splitlines()
            self.assertIn('replace=content',lines)
            self.assertIn('content=echo.omwaddon',lines)
            self.assertNotIn('Morrowind.esm',config)
            self.assertNotIn('echo-tests.omwscripts',config)

    def test_player_preferences_survive_repeated_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            profile=Path(directory)
            launcher.configure(profile,False)
            preferences='[Video]\nfullscreen = true\nresolution x = 1920\n'
            (profile/'settings.cfg').write_text(preferences,encoding='utf-8')
            launcher.configure(profile,False)
            self.assertEqual((profile/'settings.cfg').read_text(encoding='utf-8'),preferences)

    def test_tests_have_separate_content_and_sound_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            profile=Path(directory)
            launcher.configure(profile,True)
            config=(profile/'openmw.cfg').read_text(encoding='utf-8')
            self.assertIn('content=echo-tests.omwscripts',config)
            self.assertIn('no-sound=1',config)
            self.assertIn('vsync = false',(profile/'settings.cfg').read_text(encoding='utf-8'))


class ProcessTests(unittest.TestCase):
    def test_windows_cleanup_uses_process_handles(self):
        process=mock.Mock()
        process.poll.return_value=None
        with mock.patch.object(launcher.os,'name','nt'),mock.patch.object(launcher.os,'killpg',create=True) as killpg:
            launcher.stop(process)
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=3)
        killpg.assert_not_called()

    def test_windows_hung_process_is_killed(self):
        process=mock.Mock()
        process.poll.return_value=None
        process.wait.side_effect=[subprocess.TimeoutExpired('engine',3),0]
        with mock.patch.object(launcher.os,'name','nt'):
            launcher.stop(process)
        process.kill.assert_called_once()


if __name__=='__main__':
    unittest.main()

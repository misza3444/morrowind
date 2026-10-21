"""A stale or corrupt build must never advance the downloadable update feed."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import publish_windows


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.dist=self.root/'dist'
        self.dist.mkdir()
        self.revision='a'*40
        self.head=self.revision
        self.calls=[]
        bundle=self.dist/'game-bundle.zip'
        bundle.write_bytes(b'valid archive')
        release={'revision':self.revision,'release_tag':'windows-version','bundles':[
            {'asset':bundle.name,'size':bundle.stat().st_size,'sha256':hashlib.sha256(bundle.read_bytes()).hexdigest()}]}
        (self.dist/'update.json').write_text(json.dumps(release))
        for name in ('LowcaEcha-Windows-x64.zip','LowcaEcha-Launcher-Windows-x64.zip'):
            path=self.dist/name
            path.write_bytes(b'portable package')
            path.with_suffix('.zip.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+name+'\n')

    def fake_gh(self,*args,**kwargs):
        self.calls.append(args)
        if args[0]=='api':
            return subprocess.CompletedProcess(args,0,stdout=self.head+'\n')
        if args[:2]==('release','view'):
            return subprocess.CompletedProcess(args,1,stdout='')
        return subprocess.CompletedProcess(args,0,stdout='')

    def publish(self):
        with mock.patch.object(publish_windows,'ROOT',self.root), mock.patch.object(publish_windows,'gh',side_effect=self.fake_gh), mock.patch.dict('os.environ',{'GITHUB_SHA':self.revision}):
            publish_windows.main()

    def test_superseded_build_does_not_publish(self):
        self.head='b'*40
        self.publish()
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0][0],'api')

    def test_corrupt_bundle_cannot_change_releases(self):
        (self.dist/'game-bundle.zip').write_bytes(b'corruption')
        with self.assertRaises(RuntimeError):
            self.publish()
        self.assertFalse(any(call[0]=='release' for call in self.calls))

    def test_bundles_are_published_before_channel_is_advanced(self):
        self.publish()
        immutable=next(i for i,call in enumerate(self.calls) if call[:3]==('release','create','windows-version'))
        channel=next(i for i,call in enumerate(self.calls) if call[:3]==('release','upload','windows-latest'))
        self.assertLess(immutable,channel)
        self.assertTrue(any(str(self.dist/'update.json') in call for call in self.calls))


if __name__=='__main__':
    unittest.main()

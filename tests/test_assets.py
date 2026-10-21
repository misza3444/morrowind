"""Reject missing, edited, or unhydrated pack files before shipping art."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import build_content


class ArtIntegrityTests(unittest.TestCase):
    def test_only_verified_pack_bytes_are_staged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'Łowca Echa'
            (root/'assets').mkdir(parents=True)
            cache = root/'downloaded-pack'
            cache.mkdir()
            source = cache/'model.dae'
            original = b'<COLLADA>\nverified model bytes\n</COLLADA>\n'
            # Reproduce Git for Windows checking out text models with CRLF.
            source.write_bytes(original.replace(b'\n', b'\r\n'))
            manifest = {'files': [{'source': 'model.dae', 'path': 'meshes/model.dae',
                                  'sha256': hashlib.sha256(original).hexdigest()}]}
            (root/'assets/manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            output = root/'package'
            with mock.patch.object(build_content, 'ROOT', root), mock.patch.object(build_content, 'TEMPLATE', cache):
                build_content.stage_assets(output)
                self.assertEqual((output/'meshes/model.dae').read_bytes(), original)
                self.assertEqual(json.loads((output/'asset-manifest.json').read_text(encoding='utf-8')), manifest)
                for invalid in (None, b'edited model', b'version https://git-lfs.github.com/spec/v1\n'):
                    with self.subTest(invalid=invalid):
                        if invalid is None:
                            source.unlink()
                        else:
                            source.write_bytes(invalid)
                        with self.assertRaisesRegex(RuntimeError, 'run tools/setup.py'):
                            build_content.stage_assets(output)
                        self.assertEqual((output/'meshes/model.dae').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()

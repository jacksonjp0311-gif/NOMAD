"""Verify upstream bytes and projection syntax without executing downloaded code."""
import ast
import hashlib
from pathlib import Path
import unittest

from scripts import prepare_frontier_development_v18 as preparation
from nomad import frontier

ROOT=Path(__file__).resolve().parents[1]/'experiments'/'development'/'keon2733'


class DevelopmentProvenanceTests(unittest.TestCase):
    def test_original_source_and_license_match_primary_commit_bytes(self):
        raw=(ROOT/'original'/'algorithms'/'math'/'rabin_miller.py').read_bytes()
        self.assertEqual(preparation.sha(raw),preparation.SOURCE_SHA256)
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),preparation.SOURCE_GIT_BLOB)
        self.assertEqual(preparation.sha((ROOT/'original'/'LICENSE').read_bytes()),preparation.LICENSE_SHA256)
        self.assertEqual((ROOT/'projection'/'LICENSE').read_bytes(),(ROOT/'original'/'LICENSE').read_bytes())

    def test_exact_projection_preserves_docstring_and_original_function_ast(self):
        text=(ROOT/'original'/'algorithms'/'math'/'rabin_miller.py').read_text()
        projected,start,end=preparation.exact_function_projection(text,'is_prime._pow2_factor')
        self.assertEqual((start,end),(37,50))
        self.assertEqual(projected.encode(),(ROOT/'projection'/'pow2_factor.py').read_bytes())
        original=next(n for n in ast.walk(ast.parse(text)) if isinstance(n,ast.FunctionDef) and n.name=='_pow2_factor')
        extracted=next(n for n in ast.parse(projected).body if isinstance(n,ast.FunctionDef))
        self.assertEqual(ast.dump(original,include_attributes=False),ast.dump(extracted,include_attributes=False))
        self.assertIn('pow2_factor',frontier.admit_function_sources({'pow2_factor.py':projected})['modules'])


if __name__=='__main__': unittest.main()

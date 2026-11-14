"""Independent parse-only observer-boundary regressions; no payload execution."""
import unittest
from pathlib import Path
import tempfile
from nomad.frontier import admit_function_sources, inspect_function_repository


class FunctionObserverAdmissionTests(unittest.TestCase):
    def test_nonapproved_builtin_values_cannot_be_hidden_behind_approved_calls(self):
        for value in ('eval', 'exec', 'print', 'open', 'getattr', 'globals', 'locals',
                      'vars', 'compile', 'type', 'object', 'breakpoint', 'input'):
            source = f'def solve(x):\n    abs = [{value}][0]\n    return abs(x)\n'
            with self.subTest(value=value), self.assertRaises(ValueError):
                admit_function_sources({'candidate.py': source})

    def test_module_alias_cannot_be_retyped_into_generator_frame_access(self):
        files = {
            'exports.py': 'def gi_frame(): return 0\ndef f_globals(): return 0\n',
            'candidate.py': "import exports as alias\ndef solve(x):\n"
                "    alias = (item for item in [1])\n"
                "    alias = alias.gi_frame\n    alias = alias.f_globals\n"
                "    alias = alias.get('__builtins__')\n"
                "    abs = alias.get('eval')\n    return abs(x)\n"}
        with self.assertRaises(ValueError):
            admit_function_sources(files)

    def test_module_alias_cannot_be_shadowed_by_arguments_or_exception_binding(self):
        sources = (
            'import exports as alias\ndef solve(alias):\n    return alias.export()\n',
            'import exports as alias\ndef solve(x):\n    try:\n        raise ValueError(x)\n'
            '    except ValueError as alias:\n        return alias.with_traceback(None)\n',
            'import exports as alias\ndef solve(x):\n    return [alias.export() for alias in x]\n',
            'import exports as alias\ndef alias(x):\n    return x\n')
        helper = 'def export(): return 0\ndef with_traceback(x): return x\n'
        for source in sources:
            with self.subTest(source=source), self.assertRaises(ValueError):
                admit_function_sources({'exports.py': helper, 'candidate.py': source})

    def test_dunder_exports_cannot_authorize_reflective_attributes(self):
        for symbol in ('__class__', '__base__', '__subclasses__', '__globals__', '__getattr__'):
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                admit_function_sources({'exports.py': f'def {symbol}(x): return x\n'})

    def test_generator_and_function_reflection_are_not_registered_methods(self):
        for expression in ('(i for i in [1]).gi_frame', 'solve.__globals__',
                           'ValueError("x").__traceback__', 'str.format'):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                admit_function_sources({'candidate.py': f'def solve(x):\n    return {expression}\n'})

    def test_permitted_local_imports_and_collection_operations_still_admit(self):
        files = {'helpers.py': 'def twice(x):\n    return x*2\n',
                 'candidate.py': 'import helpers as module\ndef solve(values):\n'
                     '    result=[]\n    for item in values:\n'
                     '        result.append(module.twice(item))\n    return sorted(result)\n'}
        result = admit_function_sources(files)
        self.assertEqual(result['graph']['candidate.py'], ['helpers.py'])

    def test_importable_binary_and_bytecode_shadows_are_refused_before_loading(self):
        for name in ('api.abi3.so', 'api.pyd', 'api.DLL', 'api.dylib',
                     'api.pyc', 'api.pyo', 'module.egg', 'module.zip'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root/'api.py').write_text('def solve(x):\n    return x\n', encoding='utf-8')
                (root/name).write_bytes(b'inert test data; never loaded')
                with self.assertRaises(ValueError):
                    inspect_function_repository(root, [
                        {'module':'api','function':'solve','args':[1],'expected':1}])


if __name__ == '__main__':
    unittest.main()

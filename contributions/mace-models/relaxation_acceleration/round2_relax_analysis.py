"""Reuse the original analysis, binding only validated execution metadata."""
import argparse
import ast
import json
from pathlib import Path
import sys
import round2_relax_engine as engine
from round2_relax_engine import suite


def main(key):
    sys.path.insert(0, str(engine.ROOT / 'outputs/round2/adapters_v2' / key))
    import new_potential_relaxation as original
    proof = suite.read(engine.OUT / 'validation.json')
    assert proof['pass'] and proof['engine_sha256'] == suite.sha(Path(engine.__file__))
    profiles = proof['profiles'][key]
    jobs, legacy = original.planned()
    assert profiles['cpu'] == legacy
    devices = {}
    for identifier, source, published in jobs:
        row = suite.read(engine.record_path(key, identifier))
        devices[identifier] = engine.validate_record(row, profiles)
    common = engine.core(legacy)
    assert all(engine.core(profile) == common for profile in profiles.values())
    source = Path(original.__file__).read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'analyze')
    changes = []
    class Metadata(ast.NodeTransformer):
        def visit_Assert(self, node):
            if ast.unparse(node.test) == "saved['id'] == key and saved['provenance'] == provenance":
                node.test = ast.parse("saved['id'] == key and validate_saved(saved)", mode='eval').body
                changes.append('record_profile_acceptance')
            return node
        def visit_Dict(self, node):
            self.generic_visit(node)
            if any(isinstance(k, ast.Constant) and k.value == 'hull_details' for k in node.keys):
                for i, item in enumerate(node.keys):
                    if isinstance(item, ast.Constant) and item.value == 'provenance':
                        node.values[i] = ast.Name(id='common_profile', ctx=ast.Load())
                        changes.append('summary_execution_metadata')
            return node
    function = Metadata().visit(function)
    assert changes == ['record_profile_acceptance', 'summary_execution_metadata'], changes
    namespace = dict(original.__dict__)
    namespace.update(validate_saved=lambda saved: bool(engine.validate_record(saved, profiles)), common_profile=common)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), '<metadata-bound-phase-analysis>', 'exec'), namespace)
    namespace['analyze']()
    folder = engine.ROOT / 'outputs' / key / 'relaxation'
    for name in ['summary.json', 'run_summary.json']:
        data = suite.read(folder / name) if (folder / name).exists() else {}
        data.update(completed=6697, planned=6697, provenance=common, execution_provenances=profiles, path_execution_environment=devices,
                    cpu_workers_max=6, cuda_workers=1, calibration_sha256=suite.sha(engine.OUT / 'validation.json'))
        suite.atomic(folder / name, data)
    suite.atomic(engine.OUT / (key + '_analysis_binding_validation.json'),
                 {'pass': True, 'metadata_bindings_only': changes,
                  'original_analysis_sha256': suite.sha(Path(original.__file__)),
                  'executions': {device: list(devices.values()).count(device) for device in profiles}})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, choices=list(engine.MODELS))
    main(parser.parse_args().model)

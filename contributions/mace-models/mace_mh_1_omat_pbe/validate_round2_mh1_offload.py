"""Validate storage offload and the actual failing MH1 force singleton."""
import os
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
for name in ['OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS']:
    os.environ[name] = '1'
import gc
import itertools
import json
from pathlib import Path
import time
import numpy as np
import torch
import round2_mh1_force_offload as wrapper
from cuda_saved_tensor_offload import saved_tensors_on_disk
from ase.stress import voigt_6_to_full_3x3_stress
from pymatgen.core import Structure

ROOT = wrapper.ROOT
runner, helper = wrapper.runner, wrapper.helper
FIELDS = ['energy_total', 'forces', 'stress']


def compare(first, second):
    return {field: {'equal': all(np.array_equal(a[field], b[field]) for a, b in zip(first, second)),
                    'max_abs': max(float(np.max(np.abs(np.asarray(a[field]) - np.asarray(b[field])))) for a, b in zip(first, second))}
            for field in FIELDS}


def main():
    import run_round2_suite as suite
    state = suite.read(suite.STATE)
    assert state['active_gpu_owners'] == 0 and state['active_cpu_slots'] == 4
    folder = ROOT / 'outputs/round2/mace_mh_1_omat_pbe/validation'
    manifest = json.loads((ROOT / 'datasets/manifest.json').read_text())
    rows = list(itertools.islice(runner.sources.structures('matpes_pbe', manifest['matpes_pbe']['path'], start=144768), 128))
    atoms = [runner.mace.ADAPTOR.get_atoms(Structure.from_dict(row['structure'])) for row in []]
    runner.initialize('cuda')
    atoms = [runner.mace.ADAPTOR.get_atoms(Structure.from_dict(row['structure'])) for row in rows]
    original_predict = helper.predict
    failed_singletons = []
    def traced(calculator, items, batch_size):
        try:
            return original_predict(calculator, items, batch_size=batch_size)
        except RuntimeError as error:
            if 'CUDA out of memory' in str(error) and len(items) == 1:
                index = next(i for i, atom in enumerate(atoms) if atom is items[0])
                failed_singletons.append(index)
                print(json.dumps({'event': 'actual_singleton_oom', 'index': rows[index]['index'],
                                  'source_id': rows[index]['source_id'], 'atoms': len(items[0])}), flush=True)
            raise
    # Use the original retry function, not the new offload policy, to identify
    # and preserve the real singleton failure before testing its alternative.
    import ast
    import types
    tree = ast.parse((wrapper.ADAPTER / 'new_potential_force.py').read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'predict_cuda')
    namespace = dict(runner.__dict__)
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<original-predict-cuda>', 'exec'), namespace)
    helper.predict = traced
    try:
        try:
            namespace['predict_cuda'](atoms, 16)
        except RuntimeError as error:
            assert 'CUDA out of memory' in str(error) and failed_singletons
        else:
            raise AssertionError('The retained failing shard did not reproduce the singleton failure')
    finally:
        helper.predict = original_predict
    gc.collect()
    torch.cuda.empty_cache()
    dense_index = failed_singletons[0]
    # Include real structures from the failing shard that fit unmodified CUDA.
    fixtures = sorted(atoms, key=len)[:16]
    checks = []
    for deterministic in [False, True]:
        torch.use_deterministic_algorithms(deterministic)
        for size in [1, 16]:
            baseline = helper.predict(runner.mace.CALC, fixtures, batch_size=size)
            repeat = helper.predict(runner.mace.CALC, fixtures, batch_size=size)
            with saved_tensors_on_disk(ROOT / 'tmp/round2_mh1_cuda_offload') as statistics:
                offloaded = helper.predict(runner.mace.CALC, fixtures, batch_size=size)
            delta, variation = compare(baseline, offloaded), compare(baseline, repeat)
            assert all(item['max_abs'] < 1e-8 for item in delta.values())
            assert all(item['max_abs'] < 1e-8 for item in variation.values())
            if deterministic:
                assert all(item['equal'] for item in delta.values())
                assert all(item['equal'] for item in variation.values())
            check = {'deterministic': deterministic, 'batch_size': size, 'offload_difference': delta,
                     'baseline_repeat_difference': variation, 'statistics': dict(statistics)}
            checks.append(check)
            print(json.dumps({'event': 'fixture_validation', **check}), flush=True)
    torch.use_deterministic_algorithms(False)
    dense = atoms[dense_index]
    begun = time.perf_counter()
    with saved_tensors_on_disk(ROOT / 'tmp/round2_mh1_cuda_offload') as statistics:
        prediction = helper.predict(runner.mace.CALC, [dense], batch_size=1)
    dense_statistics = dict(statistics)
    dense.calc = runner.mace.CALC
    with saved_tensors_on_disk(ROOT / 'tmp/round2_mh1_cuda_offload'):
        reference = [{'energy_total': float(dense.get_potential_energy()), 'forces': dense.get_forces().copy(),
                      'stress': voigt_6_to_full_3x3_stress(dense.get_stress())}]
    delta = compare(reference, prediction)
    assert all(np.isfinite(prediction[0][field]).all() for field in FIELDS)
    assert all(item['max_abs'] < 1e-7 for item in delta.values())
    report = {'validation_pass': True, 'device': 'cuda', 'dtype': 'float64',
              'weights_sha256': runner.mace.MODEL_SHA,
              'wrapper_sha256': suite.sha(ROOT / 'round2_mh1_force_offload.py'),
              'offload_implementation_sha256': suite.sha(ROOT / 'cuda_saved_tensor_offload.py'),
              'batch_implementation_sha256': suite.sha(wrapper.ADAPTER / 'mace_batch_inference.py'),
              'validator_sha256': suite.sha(Path(__file__)), 'checks': checks,
              'dense_case': {'index': rows[dense_index]['index'], 'source_id': rows[dense_index]['source_id'],
                             'atoms': len(dense), 'original_singleton_oom': True,
                             'all_fields_finite': True, 'direct_ASE_differences': delta,
                             'statistics': dense_statistics, 'seconds': time.perf_counter() - begun}}
    suite.atomic(wrapper.PROOF, report)
    print(json.dumps({'event': 'validation_passed', 'dense_case': report['dense_case']}), flush=True)


if __name__ == '__main__':
    main()

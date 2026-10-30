"""Compare full unchanged FIRE trajectories and timings on CPU and CUDA."""
import os
for name in ['OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS']:
    os.environ[name] = '1'
import argparse
import json
from pathlib import Path
import numpy as np
import round2_relax_engine as engine
from round2_relax_engine import suite


def compare(first, second):
    assert first['result']['status'] == second['result']['status']
    assert first['result']['n_steps'] == second['result']['n_steps']
    differences = {}
    for field in ['energy_total', 'forces']:
        delta = float(np.max(np.abs(np.asarray(first['result'][field]) - np.asarray(second['result'][field]))))
        assert delta < 1e-7, (field, delta)
        differences[field] = delta
    from pymatgen.core import Structure
    a, b = (Structure.from_dict(row['result']['relaxed_structure']) for row in [first, second])
    differences['positions'] = float(np.max(np.abs(a.cart_coords - b.cart_coords)))
    assert differences['positions'] < 1e-6
    assert np.array_equal(a.lattice.matrix, b.lattice.matrix)
    return differences


def main(device):
    if device == 'cuda':
        state = suite.read(suite.STATE)
        assert state['active_gpu_owners'] == 0, 'Wait for the scheduled GPU job to release its device'
    model = engine.Engine(device)
    jobs = {job[0]: job for job in engine.jobs()}
    report = {'device': device, 'engine_sha256': suite.sha(Path(engine.__file__)), 'models': {}}
    for key in engine.MODELS:
        identifiers = suite.read(suite.OUT / key / 'validation/relaxation_acceleration_fixture_ids.json')
        records = []
        for identifier in identifiers:
            folder = engine.OUT / 'calibration' / key / device
            saved, frames = model.compute(key, jobs[identifier], folder=folder, trace=True)
            original = suite.read(engine.record_path(key, identifier))
            delta = compare(original, saved)
            item = {'id': identifier, 'seconds': saved['execution']['wall_seconds'],
                    'original_CPU_difference': delta, 'steps': saved['result']['n_steps'],
                    'path': engine.record_path(key, identifier, folder).relative_to(engine.ROOT).as_posix()}
            if device == 'cuda':
                cpu_path = engine.record_path(key, identifier, engine.OUT / 'calibration' / key / 'cpu')
                cpu = suite.read(cpu_path)
                cpu_frames = suite.read(cpu_path.with_name(cpu_path.stem + '.trace.json'))
                assert len(cpu_frames) == len(frames)
                maxima = {field: max(float(np.max(np.abs(np.asarray(a[field]) - np.asarray(b[field]))))
                                      for a, b in zip(cpu_frames, frames)) for field in ['positions', 'forces', 'energy']}
                assert maxima['positions'] < 1e-6 and maxima['forces'] < 1e-7 and maxima['energy'] < 1e-7, maxima
                assert [(f['step'], f['dt'], f['a']) for f in frames] == [(f['step'], f['dt'], f['a']) for f in cpu_frames]
                item.update(full_trajectory_maxima=maxima, cpu_seconds=cpu['execution']['wall_seconds'],
                            speedup=cpu['execution']['wall_seconds'] / saved['execution']['wall_seconds'])
            records.append(item)
            print(json.dumps({'model': key, 'device': device, **item}), flush=True)
        report['models'][key] = {'profile': model.profile(key), 'cases': records}
        if device == 'cuda':
            model.force_offload = True
            identifier = identifiers[-1]
            forced, forced_frames = model.compute(key, jobs[identifier], folder=engine.OUT / 'calibration' / key / 'cuda_forced_storage', trace=True)
            regular = suite.read(engine.ROOT / records[-1]['path'])
            regular_path = engine.ROOT / records[-1]['path']
            regular_frames = suite.read(regular_path.with_name(regular_path.stem + '.trace.json'))
            difference = compare(regular, forced)
            assert len(forced_frames) == len(regular_frames)
            trajectory_delta = max(float(np.max(np.abs(np.asarray(a['positions']) - np.asarray(b['positions']))))
                                   for a, b in zip(regular_frames, forced_frames))
            assert trajectory_delta < 1e-6
            assert sum(item['saved_tensors'] for item in forced['execution']['offload_events']) > 0
            report['models'][key]['forced_storage'] = {'pass': True, 'differences': difference,
                'trajectory_max_position_difference': trajectory_delta,
                'offloaded_force_evaluations': len(forced['execution']['offload_events'])}
            model.force_offload = False
    report['pass'] = True
    suite.atomic(engine.OUT / ('calibration_' + device + '.json'), report)
    print(json.dumps({'calibration_pass': True, 'device': device}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', choices=['cpu', 'cuda'], required=True)
    main(parser.parse_args().device)

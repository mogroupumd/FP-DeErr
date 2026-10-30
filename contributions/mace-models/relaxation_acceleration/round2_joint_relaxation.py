"""RAM-bounded CPU pool plus disjoint validated CUDA relaxation queue."""
import os
for name in ['OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS']:
    os.environ[name] = '1'
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import json
from pathlib import Path
import subprocess
import time
import uuid
import psutil
import round2_relax_engine as engine
from round2_relax_engine import suite

CPU = None


def initialize_cpu():
    global CPU
    CPU = engine.Engine('cpu')


def compute_cpu(key, job):
    saved, frames = CPU.compute(key, job)
    return {'model': key, 'id': saved['id'], 'status': saved['result']['status']}


def pick(pending, cuda=False):
    if cuda:
        return max(pending, key=lambda item: (len(pending[item][1]['initial_structure']['sites']) *
                                             (2 if item[0] == 'mace_mh_1_omat_pbe' else 1), item))
    return min(pending, key=lambda item: (len(pending[item][1]['initial_structure']['sites']), item))


def main(workers):
    proof = suite.read(engine.OUT / 'validation.json')
    assert proof['pass'] and proof['engine_sha256'] == suite.sha(Path(engine.__file__))
    tasks = engine.jobs()
    pending, completed, device_counts = {}, {}, {}
    for key in engine.MODELS:
        completed[key], device_counts[key] = {}, {'cpu': 0, 'cuda': 0}
        for job in tasks:
            path = engine.record_path(key, job[0])
            if path.exists():
                saved = suite.read(path)
                device = engine.validate_record(saved, proof['profiles'][key])
                assert saved['result']['status'] != 'failed'
                completed[key][job[0]] = saved['result']['status']
                device_counts[key][device] += 1
            else:
                pending[key, job[0]] = job
    queue = engine.OUT / 'gpu_queue'
    queue.mkdir(parents=True, exist_ok=True)
    assert not (queue / 'manager_ready.json').exists(), 'Inspect and archive a previous manager queue before resuming'
    run_id = uuid.uuid4().hex
    suite.atomic(queue / 'manager_ready.json', {'run_id': run_id,
                 'manager': {'pid': os.getpid(), 'created': psutil.Process().create_time()}})
    begun = time.perf_counter()
    futures, busy, gpu_task = {}, set(), None
    last_progress = 0
    def accept(key, identifier, status, device):
        assert (key, identifier) in busy and identifier not in completed[key]
        assert status != 'failed', (key, identifier)
        busy.remove((key, identifier))
        completed[key][identifier] = status
        device_counts[key][device] += 1
    def publish():
        for key in engine.MODELS:
            values = list(completed[key].values())
            suite.atomic(engine.ROOT / 'outputs' / key / 'relaxation/progress.json',
                         {'completed': len(values), 'planned': 6697, 'success': values.count('success'),
                          'non_converged': values.count('non_converged'), 'failed': values.count('failed'),
                          'elapsed_seconds': time.perf_counter() - begun,
                          'execution_counts': device_counts[key], 'cpu_workers_max': workers})
        suite.atomic(engine.OUT / 'dispatcher_status.json', {'state': 'running', 'updated_utc': suite.now(),
                     'pending': len(pending), 'busy': [list(item) for item in busy], 'execution_counts': device_counts,
                     'available_RAM_GiB': psutil.virtual_memory().available / 2**30})
    publish()
    with ProcessPoolExecutor(max_workers=workers, initializer=initialize_cpu) as pool:
        while pending or busy:
            if gpu_task is not None:
                assert suite.same_process(suite.read(queue / 'ready.json')), 'CUDA relaxation worker ended; inspect its retained record and log'
            if gpu_task is not None and (queue / 'done.json').exists():
                done = suite.read(queue / 'done.json')
                if done['task_id'] == gpu_task['task_id']:
                    accept(done['model'], done['id'], done['status'], 'cuda')
                    gpu_task = None
            if gpu_task is None and pending and (queue / 'ready.json').exists():
                ready = suite.read(queue / 'ready.json')
                assert ready['run_id'] == run_id and suite.same_process(ready)
                item = pick(pending, cuda=True)
                job = pending.pop(item)
                assert item not in busy
                busy.add(item)
                gpu_task = {'run_id': run_id, 'task_id': uuid.uuid4().hex, 'model': item[0], 'job': job}
                suite.atomic(queue / 'task.json', gpu_task)
            while pending and len(futures) < workers and psutil.virtual_memory().available > (5 if futures else 3.5) * 2**30:
                item = pick(pending)
                job = pending.pop(item)
                assert item not in busy
                busy.add(item)
                futures[pool.submit(compute_cpu, item[0], job)] = item
            if futures:
                finished, rest = wait(futures, timeout=.1, return_when=FIRST_COMPLETED)
                for future in finished:
                    row = future.result()
                    item = futures.pop(future)
                    assert (row['model'], row['id']) == item
                    accept(*item, row['status'], 'cpu')
            else:
                time.sleep(.1)
            if time.perf_counter() - last_progress > 2:
                publish(); last_progress = time.perf_counter()
    assert all(len(value) == 6697 for value in completed.values())
    suite.atomic(queue / 'task.json', {'run_id': run_id, 'task_id': uuid.uuid4().hex, 'stop': True})
    if not (queue / 'ready.json').exists():
        suite.atomic(engine.OUT / 'gpu_assist_summary.json', {'complete': True, 'cuda_structures': 0,
            'engine_sha256': suite.sha(Path(engine.__file__)), 'validation_sha256': suite.sha(engine.OUT / 'validation.json')})
    publish()
    for key in engine.MODELS:
        subprocess.run([str(engine.ROOT / '.venv-mace/Scripts/python.exe'), '-u',
                        str(engine.ROOT / 'round2_relax_analysis.py'), '--model', key], cwd=engine.ROOT,
                       creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    suite.atomic(engine.OUT / 'dispatcher_status.json', {'state': 'complete', 'updated_utc': suite.now(),
                                                       'execution_counts': device_counts})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=6)
    main(parser.parse_args().workers)

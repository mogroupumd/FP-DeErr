"""One persistent CUDA relaxation worker owned by the suite GPU scheduler."""
import os
for name in ['OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS']:
    os.environ[name] = '1'
import json
from pathlib import Path
import time
import os
import psutil
import round2_relax_engine as engine
from round2_relax_engine import suite


def main():
    proof = suite.read(engine.OUT / 'validation.json')
    assert proof['pass'] and proof['engine_sha256'] == suite.sha(Path(engine.__file__))
    summary_path = engine.OUT / 'gpu_assist_summary.json'
    if summary_path.exists():
        summary = suite.read(summary_path)
        assert summary['complete'] and summary['engine_sha256'] == suite.sha(Path(engine.__file__))
        return
    queue = engine.OUT / 'gpu_queue'
    while not (queue / 'manager_ready.json').exists():
        time.sleep(.2)
    config = suite.read(queue / 'manager_ready.json')
    assert suite.same_process(config['manager'])
    model = engine.Engine('cuda')
    for key in engine.MODELS:
        assert model.profile(key) == proof['profiles'][key]['cuda']
    suite.atomic(queue / 'ready.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(),
                                      'run_id': config['run_id'], 'device': 'cuda'})
    previous = None
    completed = 0
    while True:
        assert suite.same_process(config['manager']), 'Relaxation manager ended; no new task accepted'
        task_path = queue / 'task.json'
        if not task_path.exists():
            time.sleep(.05); continue
        task = suite.read(task_path)
        if task['task_id'] == previous:
            time.sleep(.05); continue
        assert task['run_id'] == config['run_id']
        if task.get('stop'):
            break
        saved, frames = model.compute(task['model'], task['job'])
        previous = task['task_id']
        completed += 1
        suite.atomic(queue / 'done.json', {'task_id': previous, 'model': task['model'],
                                          'id': saved['id'], 'status': saved['result']['status']})
    suite.atomic(engine.OUT / 'gpu_assist_summary.json', {'complete': True, 'cuda_structures': completed,
        'engine_sha256': suite.sha(Path(engine.__file__)), 'validation_sha256': suite.sha(engine.OUT / 'validation.json')})


if __name__ == '__main__':
    main()

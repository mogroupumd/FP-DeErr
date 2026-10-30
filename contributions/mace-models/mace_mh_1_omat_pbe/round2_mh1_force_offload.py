"""MH1 CUDA force continuation; offload saved tensors only on singleton OOM.

All predictions retain the original float64 CUDA model/graphs/metric functions.
Completed batches and existing shards are preserved. Each offloaded source
index, validation hash and storage statistics is recorded in shard metadata.
"""
import argparse
from collections import deque
import gc
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
KEY = 'mace_mh_1_omat_pbe'
ADAPTER = ROOT / 'outputs/round2/adapters_v2' / KEY
sys.path.insert(0, str(ADAPTER))
import new_potential_force as runner
import mace_batch_inference as helper
from cuda_saved_tensor_offload import saved_tensors_on_disk

PROOF = ROOT / 'outputs/round2' / KEY / 'validation/mace_cuda_disk_offload_validation.json'


def recover_singleton(atoms):
    proof = json.loads(PROOF.read_text())
    assert proof['validation_pass'] and proof['dtype'] == 'float64' and proof['device'] == 'cuda'
    assert proof['weights_sha256'] == runner.mace.MODEL_SHA
    assert proof['wrapper_sha256'] == runner.reproduce.sha(Path(__file__))
    assert proof['offload_implementation_sha256'] == runner.reproduce.sha(ROOT / 'cuda_saved_tensor_offload.py')
    assert proof['batch_implementation_sha256'] == runner.reproduce.sha(ADAPTER / 'mace_batch_inference.py')
    with saved_tensors_on_disk(ROOT / 'tmp/round2_mh1_cuda_offload') as statistics:
        predictions = helper.predict(runner.mace.CALC, atoms, batch_size=1)
    return predictions, dict(statistics)


def predict_cuda(atoms, batch_size):
    import torch
    results, events = [], []
    for offset in range(0, len(atoms), batch_size):
        pending = deque([(offset, atoms[offset:offset + batch_size])])
        while pending:
            first, part = pending.popleft()
            retry = singleton = False
            try:
                results.extend(helper.predict(runner.mace.CALC, part, batch_size=len(part)))
            except RuntimeError as error:
                wrapped = ('The following operation failed in the TorchScript interpreter.' in str(error)
                           and 'RuntimeError: CUDA out of memory.' in str(error))
                if not isinstance(error, torch.cuda.OutOfMemoryError) and not wrapped:
                    raise
                if len(part) == 1:
                    singleton = True
                else:
                    split = len(part) // 2
                    pending.appendleft((first + split, part[split:]))
                    pending.appendleft((first, part[:split]))
                    events.append({'offset': first, 'structures': len(part), 'retry_batch_size': split})
                retry = True
            # Leave the exception scope before collecting its CUDA graph.
            if retry:
                gc.collect()
                torch.cuda.empty_cache()
            if singleton:
                recovered, statistics = recover_singleton(part)
                assert len(recovered) == 1
                results.extend(recovered)
                events.append({'offset': first, 'structures': 1, 'retry_batch_size': 1,
                               'saved_tensor_storage': 'disk', 'arithmetic_device': 'cuda', 'dtype': 'float64',
                               'validation_sha256': runner.reproduce.sha(PROOF),
                               'wrapper_sha256': runner.reproduce.sha(Path(__file__)),
                               'storage_statistics': statistics})
    assert len(results) == len(atoms)
    return results, events


# Windows spawned workers import this module too, installing the same bounded
# retry policy. The original shard writer/standardization code is unchanged.
runner.predict_cuda = predict_cuda


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', required=True, choices=['matpes_pbe', 'omat24'])
    parser.add_argument('--device', choices=['cuda'], default='cuda')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    proof = json.loads(PROOF.read_text())
    assert proof['validation_pass'] and proof['wrapper_sha256'] == runner.reproduce.sha(Path(__file__))
    print(json.dumps({'offload_policy': 'singleton OOM only', 'device': 'cuda', 'dtype': 'float64',
                      'wrapper_sha256': runner.reproduce.sha(Path(__file__)),
                      'validation_sha256': runner.reproduce.sha(PROOF)}), flush=True)
    runner.run(args)


if __name__ == '__main__':
    main()

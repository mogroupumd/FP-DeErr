"""Check ordering, OOM-only offload, and propagation of unrecoverable errors."""
import json
from pathlib import Path
import tempfile
import torch
import round2_mh1_force_offload as wrapper
import run_round2_suite as suite


def main():
    original_predict, original_recover, original_proof = wrapper.helper.predict, wrapper.recover_singleton, wrapper.PROOF
    calls, recoveries = [], []
    wrapped = 'The following operation failed in the TorchScript interpreter.\nRuntimeError: CUDA out of memory.'
    kind, fail_recovery = 'direct', False
    def predict(calculator, atoms, batch_size):
        calls.append((list(atoms), batch_size))
        if (atoms[0] == 16 and len(atoms) > 8) or atoms == [-1]:
            if kind == 'direct':
                raise torch.cuda.OutOfMemoryError('simulated allocation failure')
            raise RuntimeError(wrapped)
        if atoms == [-2]:
            raise RuntimeError('unrelated scientific failure')
        return [{'id': item} for item in atoms]
    def recover(atoms):
        recoveries.append(list(atoms))
        if fail_recovery:
            raise RuntimeError('offloaded singleton still failed')
        return [{'id': atoms[0]}], {'saved_tensors': 1, 'unpack_calls': 1, 'saved_tensor_bytes': 100}
    with tempfile.TemporaryDirectory() as temporary:
        wrapper.PROOF = Path(temporary) / 'proof.json'
        wrapper.PROOF.write_text('{}')
        wrapper.helper.predict, wrapper.recover_singleton = predict, recover
        try:
            for kind in ['direct', 'wrapped']:
                calls.clear(); recoveries.clear()
                result, events = wrapper.predict_cuda(list(range(40)), 16)
                assert [row['id'] for row in result] == list(range(40))
                assert [len(items) for items, size in calls] == [16, 16, 8, 8, 8]
                assert not recoveries and events == [{'offset': 16, 'structures': 16, 'retry_batch_size': 8}]
                result, events = wrapper.predict_cuda([-1], 16)
                assert result == [{'id': -1}] and recoveries == [[-1]]
                assert events[0]['saved_tensor_storage'] == 'disk' and events[0]['arithmetic_device'] == 'cuda'
                fail_recovery = True
                try:
                    wrapper.predict_cuda([-1], 16)
                except RuntimeError as error:
                    assert str(error) == 'offloaded singleton still failed'
                else:
                    raise AssertionError('Unrecoverable singleton was skipped')
                fail_recovery = False
            recoveries.clear()
            try:
                wrapper.predict_cuda([-2], 16)
            except RuntimeError as error:
                assert str(error) == 'unrelated scientific failure' and not recoveries
            else:
                raise AssertionError('Unrelated failure was masked')
        finally:
            wrapper.helper.predict, wrapper.recover_singleton, wrapper.PROOF = original_predict, original_recover, original_proof
    proof = {'validation_pass': True, 'ordering_and_successful_partitions_preserved': True,
             'direct_and_wrapped_singleton_oom_offloaded': True,
             'unrecoverable_and_unrelated_failures_propagate': True,
             'wrapper_sha256': suite.sha(Path(wrapper.__file__)), 'validator_sha256': suite.sha(Path(__file__))}
    suite.atomic(wrapper.PROOF.with_name('mace_cuda_disk_offload_retry_validation.json'), proof)
    print(json.dumps(proof), flush=True)


if __name__ == '__main__':
    main()

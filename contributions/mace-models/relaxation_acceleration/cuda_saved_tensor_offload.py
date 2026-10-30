"""Disk storage for saved CUDA tensors; all arithmetic remains on CUDA.

Used only after a singleton exhausts the GPU allocator. Each saved tensor is
copied without a dtype conversion, serialized, and restored to its original
device when autograd requests it. Temporary files are scoped to one inference.
"""
from contextlib import contextmanager
from pathlib import Path
import tempfile


@contextmanager
def saved_tensors_on_disk(directory, minimum_bytes=1024 * 1024):
    import torch
    Path(directory).mkdir(parents=True, exist_ok=True)
    statistics = {'saved_tensors': 0, 'saved_tensor_bytes': 0,
                  'unpack_calls': 0, 'minimum_bytes': minimum_bytes}
    with tempfile.TemporaryDirectory(prefix='cuda-autograd-', dir=directory) as temporary:
        def pack(tensor):
            size = tensor.numel() * tensor.element_size()
            if tensor.device.type != 'cuda' or size < minimum_bytes:
                return ('resident', tensor.detach())
            path = Path(temporary) / f"{statistics['saved_tensors']:07d}.pt"
            host = tensor.detach().to('cpu')
            torch.save(host, path)
            statistics['saved_tensors'] += 1
            statistics['saved_tensor_bytes'] += size
            return ('disk', str(path), tensor.device)

        def unpack(packed):
            if packed[0] == 'resident':
                return packed[1]
            statistics['unpack_calls'] += 1
            host = torch.load(packed[1], map_location='cpu', weights_only=True)
            return host.to(packed[2])

        with torch.autograd.graph.saved_tensors_hooks(pack, unpack):
            yield statistics

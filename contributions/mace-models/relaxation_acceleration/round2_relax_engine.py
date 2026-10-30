"""Exact upstream FIRE/calculator calls with explicit CPU/CUDA execution profiles."""
import gc
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
import run_round2_suite as suite

ROOT, OUT = suite.ROOT, suite.OUT / 'relaxation_acceleration'
MODELS = suite.read(ROOT / 'round2_scope.json')['models']


def jobs():
    import relaxation_runner as base
    return [(key, source, {}) for key, source, published in base.plan_jobs('all')[0]]


def legacy(key):
    return suite.read(ROOT / 'outputs' / key / 'relaxation/plan.json')['provenance']


def record_path(key, identifier, folder=None):
    directory = Path(folder) if folder else ROOT / 'outputs' / key / 'relaxation'
    return directory / 'records' / (hashlib.sha256(identifier.encode()).hexdigest() + '.json')


def core(profile):
    return {key: value for key, value in profile.items() if key not in ['device', 'versions']}


def validate_record(record, profiles):
    matches = [device for device, profile in profiles.items() if record['provenance'] == profile]
    assert len(matches) == 1, 'Unrecognized relaxation execution provenance'
    device = matches[0]
    if device == 'cuda':
        execution = record['execution']
        assert execution['device'] == 'cuda' and execution['dtype'] == 'float64'
        assert execution['engine_sha256'] == suite.sha(Path(__file__))
    elif 'execution' in record:
        assert record['execution']['device'] == 'cpu' and record['execution']['dtype'] == 'float64'
    return device


class Engine:
    def __init__(self, device, force_offload=False):
        import torch
        from mace.calculators import MACECalculator
        from pymatgen.io.ase import AseAtomsAdaptor
        import relaxation_runner as base
        self.torch, self.Calculator, self.adaptor, self.base = torch, MACECalculator, AseAtomsAdaptor(), base
        self.device, self.force_offload = device, force_offload
        self.calculators, self.events = {}, []
        torch.set_num_threads(1)
        if device == 'cuda':
            assert torch.cuda.is_available()
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            torch.cuda.set_per_process_memory_fraction(.9)
        self.versions = {p: importlib.metadata.version(p) for p in next(iter(MODELS.values())) and legacy(next(iter(MODELS)))['versions']}
        for package, version in legacy(next(iter(MODELS)))['versions'].items():
            if package == 'torch' and device == 'cuda':
                assert self.versions[package] == version + '+cu126'
            else:
                assert self.versions[package] == version, (package, self.versions[package], version)

    def profile(self, key):
        value = dict(legacy(key))
        value.update(device=self.device, versions=self.versions)
        assert core(value) == core(legacy(key))
        return value

    def calculator(self, key):
        if key not in self.calculators:
            model = MODELS[key]
            path = ROOT / 'models' / model['checkpoint']
            assert suite.sha(path) == model['sha256']
            calc = self.Calculator(model_paths=str(path), device=self.device,
                                   default_dtype='float64', head=model['head'])
            assert calc.head == model['head'] and calc.r_max == 6.0
            assert calc.default_dtype == 'float64' and not calc.use_compile and calc.num_models == 1
            if self.device == 'cuda':
                original = calc.calculate
                def calculate(*args, **kwargs):
                    needed = self.force_offload
                    if not needed:
                        try:
                            return original(*args, **kwargs)
                        except RuntimeError as error:
                            if not isinstance(error, self.torch.cuda.OutOfMemoryError) and 'CUDA out of memory' not in str(error):
                                raise
                            needed = True
                    if needed:
                        gc.collect()
                        self.torch.cuda.empty_cache()
                        from cuda_saved_tensor_offload import saved_tensors_on_disk
                        with saved_tensors_on_disk(ROOT / 'tmp/round2_relax_offload') as statistics:
                            result = original(*args, **kwargs)
                        self.events.append(dict(statistics))
                        return result
                calc.calculate = calculate
            self.calculators[key] = calc
        return self.calculators[key]

    def compute(self, key, job, folder=None, trace=False):
        base = self.base
        directory = Path(folder) if folder else ROOT / 'outputs' / key / 'relaxation'
        assert not record_path(key, job[0], directory).exists(), 'Refuse to overwrite a completed trajectory'
        base.OUT, base.RECORDS = directory, directory / 'records'
        base.CALC, base.ADAPTOR = self.calculator(key), self.adaptor
        namespace = {'calc': base.CALC, 'adaptor': base.ADAPTOR}
        exec(base.upstream_energy_source(), namespace)
        base.ENERGY = namespace['get_energy']
        self.events = []
        frames = []
        import ase.optimize
        original_fire = ase.optimize.FIRE
        if trace:
            class TracedFIRE(original_fire):
                def __init__(optimizer, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    def capture():
                        frames.append({'step': optimizer.nsteps,
                                       'positions': optimizer.atoms.get_positions().tolist(),
                                       'forces': optimizer.atoms.get_forces().tolist(),
                                       'energy': float(optimizer.atoms.get_potential_energy()),
                                       'dt': float(optimizer.dt), 'a': float(optimizer.a),
                                       'velocity': None if optimizer.v is None else optimizer.v.tolist()})
                    optimizer.attach(capture, interval=1)
            ase.optimize.FIRE = TracedFIRE
        begun = time.perf_counter()
        try:
            result = base.compute(job, self.profile(key))
        finally:
            ase.optimize.FIRE = original_fire
        path = record_path(key, job[0], directory)
        saved = suite.read(path)
        saved['execution'] = {'device': self.device, 'dtype': 'float64', 'head': MODELS[key]['head'],
                              'engine_sha256': suite.sha(Path(__file__)),
                              'versions': self.versions, 'threads': 1,
                              'offload_events': self.events,
                              'wall_seconds': time.perf_counter() - begun}
        suite.atomic(path, saved)
        if trace:
            suite.atomic(path.with_name(path.stem + '.trace.json'), frames)
        assert saved['result']['status'] != 'failed', saved['result']
        return saved, frames

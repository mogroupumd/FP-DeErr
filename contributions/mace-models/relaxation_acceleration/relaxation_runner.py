"""Fresh CHGNet fixed-cell relaxation using FP-DeErr's exact ENERGY_FUNC."""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
import textwrap
import time

import reproduce

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "relaxation"
RECORDS = OUT / "records"
CALC = None
ENERGY = None
ADAPTOR = None


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    # Runtime recovery checkpoints retain every value but need no pretty-print
    # whitespace. This reduces per-optimizer-step disk traffic.
    compact = path.name == 'runtime_checkpoint.json'
    tmp.write_text(json.dumps(value, indent=None if compact else 2,
                              separators=(',', ':') if compact else None, allow_nan=False,
                              default=lambda v: v.tolist() if hasattr(v, "tolist") else v.as_dict()), encoding="utf-8")
    # Windows readers/antivirus can briefly hold a destination handle.
    for attempt in range(20):
        try:
            tmp.replace(path)
            break
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def record_path(key):
    return RECORDS / (hashlib.sha256(key.encode()).hexdigest() + ".json")


def upstream_energy_source():
    notebook = reproduce.REPO / "Phase_stability_ordering/generation/convexhull_ordering_run_generator.ipynb"
    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    for cell in cells:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if "ENERGY_FUNC =" not in source:
            continue
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ENERGY_FUNC" for t in node.targets):
                # ENERGY_FUNC = textwrap.dedent(<literal>).strip()
                literal = node.value.func.value.args[0]
                return textwrap.dedent(ast.literal_eval(literal)).strip()
    raise RuntimeError("Upstream ENERGY_FUNC not found")


def initialize(threads):
    global CALC, ENERGY, ADAPTOR
    import torch
    from chgnet.model.model import CHGNet
    from chgnet.model.dynamics import CHGNetCalculator
    from chgnet.graph.converter import CrystalGraphConverter
    from pymatgen.io.ase import AseAtomsAdaptor

    torch.set_num_threads(threads)
    weights = ROOT / ".venv/Lib/site-packages/chgnet/pretrained/0.3.0/chgnet_0.3.0_e29f68s314m37.pth.tar"
    assert reproduce.sha(weights) == "d14ab7c0f093efe64b60a7bcd540bca10e74fb7f46c86108a079af60524659d1"
    model = CHGNet.from_dict(torch.load(weights, map_location="cpu", weights_only=False)["model"])
    model.graph_converter = CrystalGraphConverter(
        atom_graph_cutoff=model.graph_converter.atom_graph_cutoff,
        bond_graph_cutoff=model.graph_converter.bond_graph_cutoff,
        algorithm="legacy",
    )
    model.eval()
    CALC = CHGNetCalculator(model=model, use_device="cpu")
    ADAPTOR = AseAtomsAdaptor()
    namespace = {"calc": CALC, "adaptor": ADAPTOR}
    exec(upstream_energy_source(), namespace)
    ENERGY = namespace["get_energy"]


def compute(job, provenance):
    from pymatgen.core import Structure
    import numpy as np

    key, source, published = job
    begun = time.perf_counter()
    try:
        atoms = ADAPTOR.get_atoms(Structure.from_dict(source["initial_structure"]))
        result = ENERGY(atoms, static=False, fmax=0.01, max_steps=10000)
        result["n_atoms"] = len(atoms)
        result["max_force_eV_per_A"] = float(np.linalg.norm(np.asarray(result["forces"]), axis=1).max())
        result["published_energy_total"] = published.get("energy_total")
        if result["published_energy_total"] is not None:
            result["difference_meV_per_atom"] = (result["energy_total"] - result["published_energy_total"]) * 1000 / len(atoms)
        assert np.allclose(Structure.from_dict(result["relaxed_structure"]).lattice.matrix, atoms.cell.array, rtol=0, atol=1e-10)
        if result["status"] == "success":
            assert result["max_force_eV_per_A"] < 0.01
    except Exception as error:
        result = {"status": "failed", "error": repr(error)}
    result["seconds"] = time.perf_counter() - begun
    payload = {"id": key, "provenance": provenance, "result": result}
    atomic_json(record_path(key), payload)
    return {"id": key, **{k: result.get(k) for k in ["status", "n_steps", "seconds", "difference_meV_per_atom", "max_force_eV_per_A", "error"]}}


def plan_jobs(scope):
    reference, published, provenance = reproduce.data()
    source = reference["reference_data"]
    fp = published["models"]["chgnet"]
    jobs = {}
    for system, candidates in source["hull"].items():
        for cid, rec in candidates.items():
            key = "hull||" + (system if rec["role"] == "interior" else "__endpoint__") + "||" + cid
            jobs[key] = (key, rec, fp["hull"]["relax"][system][cid])
    if scope == "all":
        for group in sorted(source["ordering"]):
            for cid, rec in source["ordering"][group]["orderings"].items():
                key = "ordering||" + group + "||" + cid
                jobs[key] = (key, rec, fp["ordering"]["relax"][group][cid])
    provenance = {**provenance, "weights_sha256": "d14ab7c0f093efe64b60a7bcd540bca10e74fb7f46c86108a079af60524659d1",
                  "energy_func_sha256": hashlib.sha256(upstream_energy_source().encode()).hexdigest(),
                  "optimizer": "ASE FIRE", "fmax": 0.01, "max_steps": 10000, "fixed_cell": True,
                  "starting_geometry": "initial_structure", "graph_algorithm": "legacy", "atom_cutoff": 6, "bond_cutoff": 3}
    return list(jobs.values()), provenance


def run(args):
    jobs, provenance = plan_jobs(args.scope)
    if args.limit:
        jobs = jobs[:args.limit]
    pending = []
    complete = []
    for job in jobs:
        p = record_path(job[0])
        if p.exists():
            cached = json.loads(p.read_text(encoding="utf-8"))
            assert cached["id"] == job[0] and cached["provenance"] == provenance
            complete.append({"id": job[0], **cached["result"]})
        else:
            pending.append(job)
    print(f"PLANNED {len(jobs)}; CACHED {len(complete)}; PENDING {len(pending)}; WORKERS {args.workers}", flush=True)
    atomic_json(OUT / "plan.json", {"provenance": provenance, "scope": args.scope, "jobs": [j[0] for j in jobs], "workers": args.workers, "threads_per_worker": args.threads})
    started = time.perf_counter()
    os.environ["OMP_NUM_THREADS"] = str(args.threads)
    os.environ["MKL_NUM_THREADS"] = str(args.threads)
    os.environ["OPENBLAS_NUM_THREADS"] = str(args.threads)
    with ProcessPoolExecutor(max_workers=args.workers, initializer=initialize, initargs=(args.threads,)) as executor:
        futures = {executor.submit(compute, job, provenance): job[0] for job in pending}
        for future in as_completed(futures):
            row = future.result()
            complete.append(row)
            if len(jobs) <= 10 or len(complete) <= 3 or len(complete) % 25 == 0 or row["status"] != "success":
                print("RELAX", len(complete), "/", len(jobs), json.dumps(row), flush=True)
            atomic_json(OUT / "progress.json", {"completed": len(complete), "planned": len(jobs), "elapsed_seconds": time.perf_counter() - started,
                        "success": sum(r["status"] == "success" for r in complete), "failed": sum(r["status"] == "failed" for r in complete),
                        "non_converged": sum(r["status"] == "non_converged" for r in complete), "last": row})
    atomic_json(OUT / "run_summary.json", {"provenance": provenance, "completed": len(complete), "planned": len(jobs), "scope": args.scope,
                                          "rows": complete, "elapsed_seconds": time.perf_counter() - started})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["hull", "all"], default="hull")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--threads", type=int, default=1)
    run(parser.parse_args())

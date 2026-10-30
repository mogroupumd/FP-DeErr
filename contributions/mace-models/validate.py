"""Validate the saved MACE contribution without loading models or changing data."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1 << 20), b''):
            value.update(chunk)
    return value.hexdigest()


def main(repo):
    folder = repo / 'contributions/mace-models'
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    for relative, expected in manifest['files_sha256'].items():
        assert digest(repo / relative) == expected, relative
    models = json.loads((folder / 'checkpoints.json').read_text(encoding='utf-8'))
    neb_path = 'docs/data/ion_migration_neb_leaderboard_summary.json'
    neb = json.loads((repo / neb_path).read_text(encoding='utf-8'))
    assert (repo / neb_path).read_bytes() == (repo / 'Ion_migration_NEB/data/ion_migration_neb_leaderboard_summary.json').read_bytes()
    page = (repo / 'docs/ion-migration-neb.html').read_text(encoding='utf-8')
    count = int(re.search(r'const EXPECTED_FP_COUNT = (\d+);', page).group(1))
    assert count == len(neb['models']) == len(neb['fp_order'])
    assert len(set(neb['fp_order'])) == count
    assert [model['fp_key'] for model in neb['models']] == neb['fp_order']
    for key, model in models.items():
        audit = json.loads((folder / key / 'scientific_audit.json').read_text(encoding='utf-8'))
        assert audit['pass'] and audit['deep_source_verification']
        assert digest(folder / key / 'scientific_audit.json') == manifest['audit_sha256'][key]
        entry = next(item for item in neb['models'] if item['fp_key'] == model['fp_key'])
        assert entry['display_name'] == model['display_name'] and entry['n_total'] == 154
        assert 0 <= entry['n_nonconverged'] <= 154
        assert model['display_name'] in page
        source = next(item for item in neb['generation_metadata']['sources'] if item['fp_keys'] == [model['fp_key']])
        compressed = repo / source['source_results_file']
        assert digest(compressed) == source['source_results_sha256']
        uncompressed = hashlib.sha256()
        with gzip.open(compressed, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b''):
                uncompressed.update(chunk)
        assert uncompressed.hexdigest() == source['uncompressed_export_input_sha256']
        for dataset, expected in [('matpes_pbe', 434712), ('omat24', 117004)]:
            summary = json.loads((folder / key / (dataset + '_summary.json')).read_text(encoding='utf-8'))
            assert summary['full_dataset_complete'] and summary['structures'] == expected
            assert summary['provenance']['weights_sha256'] == model['sha256']
            with (folder / key / (dataset + '_summary_metrics.csv')).open(encoding='utf-8', newline='') as stream:
                rows = list(csv.reader(stream))
            assert rows[1][0] == model['display_name']
            assert rows[1][1:] == list(summary['summary_metrics'].values())
    print(json.dumps({'pass': True, 'models': list(models), 'neb_model_count': count,
                      'contributed_file_checksums': len(manifest['files_sha256']),
                      'compressed_result_round_trip_verified': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    main(parser.parse_args().repo.resolve())

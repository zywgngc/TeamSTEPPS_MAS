"""Fetch pinned upstream source into an ignored directory; never vendor datasets."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(*args, capture=False):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE if capture else None).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-local', type=Path, help='Optional existing MedAgents clone; uses no hardlinks.')
    parser.add_argument('--destination', type=Path, default=ROOT/'third_party/MedAgents')
    args = parser.parse_args()
    spec = json.loads((ROOT/'configs/upstream.json').read_text())['MedAgents']
    destination = args.destination.expanduser().resolve()
    if destination.exists():
        actual = run('git', '-C', str(destination), 'rev-parse', 'HEAD', capture=True).strip()
        if actual != spec['commit']:
            raise SystemExit('Existing checkout has another commit; choose a new destination. Nothing was changed.')
        if run('git', '-C', str(destination), 'status', '--porcelain', '--untracked-files=no', capture=True).strip():
            raise SystemExit('Existing checkout has changes; preserve it and choose a new destination.')
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = ['git', 'clone', '--no-checkout']
        command += ['--no-hardlinks', str(args.from_local.resolve())] if args.from_local else ['--filter=blob:none', spec['url']]
        run(*command, str(destination))
        run('git', '-C', str(destination), 'checkout', '--detach', spec['commit'])
        run('git', '-C', str(destination), 'remote', 'set-url', 'origin', spec['url'])
    for name in spec['required_files']:
        if not (destination/name).is_file():
            raise SystemExit('Required upstream file missing: ' + name)
    print(json.dumps({'name': 'MedAgents', 'commit': spec['commit'], 'path': str(destination)}))


if __name__ == '__main__':
    main()

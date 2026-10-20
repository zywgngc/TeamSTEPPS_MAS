"""Check imports and optional upstream resources; performs no inference."""
import argparse
import importlib.metadata
import json
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true')
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise SystemExit('Python3.12 or newer is required')
    import teamstepps_mas
    packages = ['httpx', 'jsonschema']
    if args.native:
        packages += ['jsonlines', 'nltk', 'rouge-score']
        from teamstepps_mas.upstream import medagents_root, prompt_module
        import nltk
        nltk.data.find('tokenizers/punkt_tab/english/')
        prompt_module()
        print('MedAgents source:', medagents_root())
    print(json.dumps({'python': sys.version.split()[0], 'package': teamstepps_mas.__version__,
                      'dependencies': {p: importlib.metadata.version(p) for p in packages},
                      'model_calls': 0}))


if __name__ == '__main__':
    main()

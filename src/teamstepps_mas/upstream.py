"""Pinned MedAgents imports and the original syn_verif control flow adapter."""
from __future__ import annotations
import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from .runtime import public_case, extract_final_choice
from .parsing import final_choice
ROOT = Path(__file__).resolve().parents[2]

def medagents_root():
    root = Path(os.environ.get('MEDAGENTS_ROOT', ROOT/'third_party/MedAgents')).expanduser().resolve()
    if not all((root/f).is_file() for f in ['utils.py','data_utils.py','prompt_generator.py']):
        raise FileNotFoundError('MedAgents source missing. Run python scripts/bootstrap_upstream.py or set MEDAGENTS_ROOT.')
    return root

def prompt_module():
    spec = importlib.util.spec_from_file_location('task_team_author_prompts_v15', medagents_root()/'prompt_generator.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def medagents(case, client, wider_limits=False, analysis_tokens=768):
    """Execute original fully_decode(syn_verif), preserving prompts, domain counts and vote loop."""
    upstream = medagents_root()
    sys.path.insert(0, str(upstream))
    spec = importlib.util.spec_from_file_location("medagents_original_utils", upstream/"utils.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    loop = asyncio.get_running_loop()

    class Handler:
        def get_output_multiagent(self, user_input, temperature, max_tokens, system_role):
            if wider_limits:
                max_tokens = max(128 if max_tokens <= 50 else analysis_tokens, max_tokens)
            return asyncio.run_coroutine_threadsafe(client.complete(
                system_role, user_input, tag="medagents:upstream", max_tokens=max_tokens,
                temperature=temperature), loop).result()

    question = case["question"]
    if case.get("context"):
        question = "\n".join(case["context"])+"\n\n"+question
    data = await asyncio.to_thread(module.fully_decode, 0, case["id"], question, case["options"], "",
                                   Handler(), SimpleNamespace(method="syn_verif", max_attempt_vote=3), None)
    return {"answer": extract_final_choice(data["raw_output"], case["options"]), "upstream": data,
            "upstream_parsed_answer": data["pred_answer"], "wider_limits": wider_limits,
            "analysis_minimum_tokens": analysis_tokens if wider_limits else None}

async def run_native_reference(case, client):
    """Fresh author syn_verif; same widened caps and final parser as V14."""
    case = public_case(case)
    result = await medagents(case, client, wider_limits=True, analysis_tokens=2048)
    result['native_scored_answer'] = result['answer']
    result['answer'] = final_choice(result['upstream']['raw_output'], case['options'])
    result.update(implementation='fresh_author_MedAgents_reference_v15', author_flow_unchanged=True,
                  cached_clinical_prefix_reused=False, independent_medical_annotations=0)
    return result

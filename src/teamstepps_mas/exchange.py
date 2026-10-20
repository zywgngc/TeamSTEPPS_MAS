"""Explicit source mapping and reversible exact-content pooling for V16 views.

Byte/structural preservation does not prove an LLM understands a pooled view.
No information is fetched by an ID: every referenced payload travels inline.
"""
from __future__ import annotations
from collections import Counter
import copy
import hashlib
import json


def canonical(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()


def source_packet(case):
    return dict(question=dict(source_id='Q',text=case['question']),
        evidence=[dict(source_id='E%d'%(i+1),text=s) for i,s in enumerate(case.get('context',[]))],
        options=[dict(source_id='O:'+k,label=k,text=v) for k,v in case['options'].items()],
        acquisition_tools=[])


def source_ids(packet):
    return ['Q',*[x['source_id'] for x in packet['evidence']],
            *[x['source_id'] for x in packet['options']]]


def inline_view(value):
    return dict(view=copy.deepcopy(value),inline_payloads={},
        reference_rule='payload_ref resolves only to inline_payloads in THIS message; not an external lookup')


def pooled_view(value):
    counts=Counter()
    def count(x):
        key=canonical(x)
        if isinstance(x,(dict,list,str)) and len(key)>=100:counts[key]+=1
        if isinstance(x,dict):
            for v in x.values():count(v)
        elif isinstance(x,list):
            for v in x:count(v)
    count(value)
    repeated={k for k,n in counts.items() if n>1};ids={};pool={}
    def encode(x,can_reference=True):
        key=canonical(x)
        if can_reference and key in repeated:
            if key not in ids:
                ref='P%d'%(len(ids)+1);ids[key]=ref;pool[ref]=encode(x,False)
            return {'payload_ref':ids[key]}
        if isinstance(x,dict):return {k:encode(v) for k,v in x.items()}
        if isinstance(x,list):return [encode(v) for v in x]
        return copy.deepcopy(x)
    result=dict(view=encode(value),inline_payloads=pool,
        reference_rule='payload_ref resolves only to inline_payloads in THIS message; not an external lookup')
    assert unpool(result)==value
    return result


def unpool(packet):
    def decode(x,stack=()):
        if isinstance(x,dict) and set(x)=={'payload_ref'}:
            ref=x['payload_ref']
            if ref in stack:raise ValueError('Cyclic pooled payload')
            return decode(packet['inline_payloads'][ref],(*stack,ref))
        if isinstance(x,dict):return {k:decode(v,stack) for k,v in x.items()}
        if isinstance(x,list):return [decode(v,stack) for v in x]
        return copy.deepcopy(x)
    return decode(packet['view'])

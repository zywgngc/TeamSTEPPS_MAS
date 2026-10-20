"""Escape-safe logical contracts and configurable bounded grammar transport."""
from __future__ import annotations
import copy
import hashlib
import json
import os
GRAMMARS = {}


def physical_schema(logical):
    if isinstance(logical, list):
        return [physical_schema(value) for value in logical]
    if not isinstance(logical, dict):
        return copy.deepcopy(logical)
    return {key: physical_schema(value) for key, value in logical.items()
        if not (logical.get('type') == 'string' and key in ('minLength', 'maxLength'))}

class GrammarBoundary:
    """Log the actual constrained request, without unbounded inter-field spaces."""
    def __init__(self, http):
        self.http = http

    def __getattr__(self, name):
        return getattr(self.http, name)

    async def post(self, url, **kwargs):
        payload = kwargs.get('json', {})
        response_format = payload.get('response_format', {})
        if response_format.get('type') == 'json_schema':
            schema = response_format['json_schema']['schema']
            key = hashlib.sha256(json.dumps(schema, separators=(',', ':')).encode()).hexdigest()
            if key not in GRAMMARS:
                response = await self.http.post(os.environ.get('SCHEMA_COMPILER_URL', 'http://127.0.0.1:24410/compile'), json={'schema': schema})
                response.raise_for_status()
                GRAMMARS[key] = response.json()['grammar']
            payload.pop('response_format')
            payload['structured_outputs'] = {'grammar': GRAMMARS[key]}
        return await self.http.post(url, **kwargs)

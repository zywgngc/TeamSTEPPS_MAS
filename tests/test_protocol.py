"""Synthetic controller regressions, never clinical effectiveness tests."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from protocol_fixtures import scenario


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_protocol_scenarios(self):
        case = dict(id='PRIVATE_FIXTURE_CASE_ID', dataset='PRIVATE_DATASET_NAME',
                    gold='SECRET_GOLD_NOT_FOR_MODEL',
                    question='Which offered choice follows from the supplied fixture?',
                    context=['Fixture value is 4, not 3.'],
                    options={'A': 'fixture first choice', 'B': 'fixture second choice', 'C': 'fixture third choice'})
        prompts = SimpleNamespace(
            get_question_domains_prompt=lambda question: ('fixture recruiter', question),
            get_options_domains_prompt=lambda question, options: ('fixture recruiter', question + str(options)),
            get_final_answer_prompt_wsyn=lambda report: 'fixture final selection\n' + report)
        cases = [('none', {}), ('closed', {}), ('persistent', {}), ('decline', {}),
                 ('closed', {'meaning_feedback': False}), ('closed', {'task_assistance': False}),
                 ('persistent', {'broadcast': True}), ('all_outside', {}), ('unselected', {}),
                 ('stress', {'broadcast': True}), ('closed', {'pool_messages': False}),
                 ('stress', {'broadcast': True, 'pool_messages': False}),
                 ('invalid_json', {}), ('output_limit', {}), ('invalid_owner_ref', {}), ('invalid_task_link', {})]
        with tempfile.TemporaryDirectory() as temporary, patch('teamstepps_mas.protocol.prompt_module', return_value=prompts):
            for i, (name, settings) in enumerate(cases):
                with self.subTest(scenario=name, settings=settings):
                    folder = Path(temporary)/str(i)
                    folder.mkdir()
                    await scenario(case, name, folder, {}, **settings)


if __name__ == '__main__':
    unittest.main()

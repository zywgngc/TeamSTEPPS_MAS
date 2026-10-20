"""Ported synthetic protocol fixtures; no clinical data, models or experimental outputs."""
from __future__ import annotations
from collections import Counter
import copy
import json
from jsonschema.exceptions import ValidationError
from teamstepps_mas.protocol import TaskTeam
from teamstepps_mas.exchange import source_packet, pooled_view, unpool, digest
from teamstepps_mas.grammar import physical_schema


def read_payload(text):
    start=0 if text.startswith('{') else text.rfind('\n{')+1
    return unpool(json.loads(text[start:]))

class FixtureClient:
    def __init__(self,case,scenario='none',path=None):
        self.case,self.scenario=case,scenario;self.path=path
        self.records=[];self.http=object();self.version=-1

    async def complete(self,system,user=None,*,messages=None,tag,max_tokens,**kwargs):
        if messages is None:
            messages=([dict(role='system',content=system)] if system else [])+[dict(role='user',content=user)]
        stage,actor=tag.split(':')[1:3] if tag.count(':')>1 else ('final','selector')
        first=next(iter(self.case['options']));reason='ENGINEERING_FIXTURE_NOT_MEDICAL'
        payload=None
        if stage not in ('recruit','final'):payload=read_payload(messages[-1]['content'])
        if stage=='recruit':
            body='Medical Field: Internal Medicine | Pharmacology | Epidemiology | Pathology | Clinical Reasoning' if actor=='Q' else 'Medical Field: Internal Medicine | Pharmacology'
        elif stage=='final':body="'''Option: %s'''"%first
        else:
            claim=lambda label:dict(statement=label,evidence_kind='background_inference',source_ids=['Q'],
                rationale=reason,conditions_and_limits=['IMPORTANT_FIXTURE_LIMIT'])
            if stage=='brief':
                value=dict(task=dict(decision=self.case['question'],criterion=reason),
                    assignments={k:reason for k in payload['recruited_roles']},resources_and_limits=reason)
            elif stage=='work':
                value=dict(status='outside_role',reason=reason) if self.scenario=='all_outside' else dict(
                    status='contribution',proposed_choice=first,decision_reason=reason,
                    claims=[claim('ORIGINAL_WORK_'+actor+'_'+str(i)) for i in range(3 if self.scenario=='stress' else 1)])
            elif stage=='synthesis':
                self.version+=1
                value=dict(current_task=dict(decision=self.case['question'],criterion=reason),
                    proposed_choice=first,report='FIXTURE_REPORT_VERSION_'+str(self.version),
                    critical_uses=[dict(claim_id=k,role_in_decision='supports',interpreted_use='INTERPRETED_'+k)
                        for k in payload['attributed_claim_registry'] if not (self.scenario=='unselected' and k=='Q1.C1')],
                    issue_responses={k:dict(position='uncertain',response=reason) for k in payload['current_issues']})
                if self.scenario=='stress':
                    registry=payload['attributed_claim_registry'];selected=[]
                    for key,item in registry.items():
                        if item['assistance_product_id'] or not any(registry[k]['owner']==item['owner'] for k in selected):selected.append(key)
                    selected=(selected+[k for k in registry if k not in selected])[:12]
                    value['critical_uses']=[dict(claim_id=k,role_in_decision='supports',interpreted_use='INTERPRETED_'+k) for k in selected]
            elif stage in ('clinical','meaning'):
                prior=payload['own_prior_issues'];v=self.version
                if stage=='clinical':
                    position=dict(status='no_concern',reason='CLINICAL_ONLY_R%d_%s'%(v,actor))
                    if (actor=='Q1' and self.scenario in ('closed','persistent','decline','invalid_task_link') and v==0) or self.scenario=='stress':
                        position=dict(status='concern',statement_or_gap='FIXTURE_CLINICAL_TARGET',
                                      reason_and_needed_work='CLINICAL_ONLY_R%d_%s'%(v,actor))
                    if actor=='Q1' and self.scenario in ('persistent','decline') and v==2:
                        position=dict(status='outside_role',reason=reason)
                    state='handled' if self.scenario=='closed' else ('not_assessed' if v==2 else 'still_open')
                else:
                    own=payload['original_currently_used_own_claims']
                    position=dict(status='accurate',reason='MEANING_ONLY_R%d_%s'%(v,actor)) if own else dict(status='not_represented',reason=reason)
                    if (actor=='Q1' and self.scenario in ('closed','persistent','invalid_owner_ref') and v==0) or self.scenario=='stress':
                        position=dict(status='misrepresented',claim_ids=['Q2.C1'] if self.scenario=='invalid_owner_ref' else [next(iter(own))],
                                      correction='MEANING_ONLY_R%d_%s'%(v,actor))
                    state='still_open' if self.scenario=='stress' else 'handled'
                value=dict(position=position,prior_issues={k:dict(state=state,reason=reason) for k in prior})
            elif stage=='huddle':
                ids=payload['issues_requiring_decision'];assign=[]
                if self.version==0 and payload['task_assistance_enabled']:
                    key=next(k for k,v in ids.items() if v['kind']=='clinical')
                    assign=[dict(owner='Q2',issue_ids=[key],operation='check_source',
                                 task='PERFORM_FIXTURE_SOURCE_CHECK',expected_product='RETURN_FIXTURE_PRODUCT')]
                if self.scenario=='stress' and payload['task_assistance_enabled']:
                    targets=[k for k,v in ids.items() if v['kind']=='clinical'][:2]
                    assign=[dict(owner=owner,issue_ids=[key],operation='check_source',
                        task='PERFORM_FIXTURE_SOURCE_CHECK',expected_product='RETURN_FIXTURE_PRODUCT')
                        for owner,key in zip(['Q2','O1'],targets)]
                acted={k for x in assign for k in x['issue_ids']}
                value=dict(issue_decisions={k:dict(position='act' if k in acted else 'pending',reason=reason) for k in ids},assignments=assign)
                if self.scenario=='invalid_task_link':
                    value['issue_decisions']={k:dict(position='pending',reason=reason) for k in ids}
            elif stage=='accept':
                value=dict(status='cannot_perform',reason='NO_ACTUAL_NEW_DATA') if self.scenario=='decline' else dict(
                    status='accept',task_readback=payload['assignment']['task'],available_steps_and_limits=reason)
            elif stage=='assistance':value=dict(status='completed',proposed_choice=first,
                findings_and_limits='ACTUAL_FIXTURE_WORK_PRODUCT',claims=[claim('ASSISTANCE_PRODUCT_CLAIM')])
            else:raise AssertionError(stage)
            body=json.dumps(value,ensure_ascii=False)
            if self.scenario=='invalid_json' and stage=='work':body='{BROKEN_FIXTURE'
        finish='length' if self.scenario=='output_limit' and stage=='work' else 'stop'
        request=dict(model='SCRIPTED_CPU_FIXTURE_NO_MODEL',messages=copy.deepcopy(messages),max_tokens=max_tokens,**kwargs)
        row=dict(tag=tag,request=request,response=dict(role='assistant',content=body),finish_reason=finish,
                 fixture_not_provider_response=True)
        self.records.append(row)
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with self.path.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        return body

def verify_received(team,client,schemas):
    calls=client.records;markers=('PRIVATE_FIXTURE_CASE_ID','PRIVATE_DATASET_NAME','SECRET_GOLD_NOT_FOR_MODEL')
    for c in calls:
        assert not any(s in json.dumps(c['request']['messages'],ensure_ascii=False) for s in markers)
    for e in team.events:
        if e['event']!='typed_request':continue
        call=calls[e['record_index']];msgs=call['request']['messages'];payload=read_payload(msgs[-1]['content'])
        assert digest(msgs)==e['actual_messages_sha256'] and digest(payload)==e['logical_payload_sha256']
        schemas[digest(physical_schema(e['logical_schema']))]=physical_schema(e['logical_schema'])
        if e['origin_record_index'] is not None:
            origin=calls[e['origin_record_index']]
            assert msgs[:-2]==origin['request']['messages']
            assert msgs[-2]==dict(role='assistant',content=origin['response']['content'])
        if 'original_source' in payload:assert payload['original_source']==source_packet(client.case)
        if e['stage'] in ('clinical','meaning'):
            history=payload.get('logical_team_history',[])
            assert not any(h['stage'] in ('clinical','meaning') and h['version']==e['version'] for h in history)
        if e['stage']=='clinical':
            assert 'actual_own_uses' not in payload
            # Current labels are not mixed into this clinical request.
            text=json.dumps(payload,ensure_ascii=False)
            assert 'MEANING_ONLY_R%d_'%e['version'] not in text
    for task in team.tasks:
        if task['status']=='cannot_perform':assert 'product_record_index' not in task
        else:
            assert task['acceptance_record_index']<task['product_record_index']
            product=calls[task['product_record_index']]
            accept=calls[task['acceptance_record_index']]
            assert product['request']['messages'][-2]['content']==accept['response']['content']
            later=[read_payload(c['request']['messages'][-1]['content']) for c in calls[task['product_record_index']+1:]
                   if c['tag'].startswith('task_team_v16:synthesis:')]
            assert any(task in p['completed_or_unavailable_assistance'] for p in later)

async def scenario(case,name,folder,schemas,**kwargs):
    client=FixtureClient(case,name,folder/(name+'.jsonl'));team=TaskTeam(case,client,**kwargs)
    if name in ('invalid_json','output_limit','invalid_owner_ref','invalid_task_link'):
        try:await team.execute()
        except (ValueError,json.JSONDecodeError,ValidationError):pass
        else:raise AssertionError('Original invalid response was repaired')
        count,tag=(19,'task_team_v16:meaning:Q1') if name=='invalid_owner_ref' else (
            (26,'task_team_v16:huddle:coordinator') if name=='invalid_task_link' else (4,'task_team_v16:work:Q1'))
        assert len(client.records)==count and client.records[-1]['tag']==tag
        return dict(scenario=name,pass_check=True,original_failure_retained=True,calls=count)
    result=await team.execute();verify_received(team,client,schemas)
    counts=Counter(c['tag'].split(':')[1] for c in client.records)
    if name=='none':assert len(result['report_versions'])==1 and not result['assistance_tasks']
    if name=='closed':
        assert len(result['report_versions'])==2 and not result['final_pending_issues']
        if kwargs.get('task_assistance',True):
            assert counts['accept']==counts['assistance']==1
            assert any(v['assistance_product_id']=='T1' for v in result['claim_registry'].values())
    if name=='persistent':
        assert result['final_pending_issues'] and all(v['kind']=='clinical' for v in result['final_pending_issues'].values())
        assert len(result['report_versions'])==3 and all(x['actual_text_changed'] for x in result['report_versions'][1:])
    if name=='decline':assert counts['accept']==1 and counts['assistance']==0 and result['final_pending_issues']
    if name=='all_outside':
        assert not result['claim_registry']
        assert all(x['position']['status']=='not_represented' for x in result['review_rounds'][0]['meaning_reviews'].values())
    if name=='unselected':
        assert 'Q1.C1' in result['claim_registry'] and 'Q1.C1' not in result['final_packet']['current_decision']['original_claims']
        assert result['review_rounds'][0]['meaning_reviews']['Q1']['position']['status']=='not_represented'
    if name=='stress':
        assert len(result['final_pending_issues'])==42 and counts['accept']==counts['assistance']==4
        assert len(result['claim_registry'])==25 and len(result['final_packet']['current_decision']['original_claims'])==12
    if not kwargs.get('meaning_feedback',True):assert counts['meaning']==0
    if not kwargs.get('task_assistance',True):assert counts['accept']==counts['assistance']==0
    return dict(scenario=name,settings=kwargs,pass_check=True,calls_by_stage=dict(counts),
                remaining_owner_reported_issues=len(result['final_pending_issues']))

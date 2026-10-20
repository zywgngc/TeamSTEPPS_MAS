"""Candidate MedAgents-derived protocol: clinical monitoring and meaning separately.

Original claims retain attribution, assistance has acceptance and actual work,
and only owners can report their issues handled. No status is medical gold.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from .grammar import physical_schema
from .grammar import GrammarBoundary
from .parsing import final_choice
from .runtime import public_case
from .upstream import prompt_module
from .exchange import digest, source_packet, source_ids, pooled_view, inline_view
from . import contracts

SKILL=Path(__file__).parent/'prompts/default.json'
TAG='task_team_v16:'


class TaskTeam:
    def __init__(self,case,client,*,meaning_feedback=True,task_assistance=True,broadcast=False,pool_messages=True,skill=None):
        self.case=copy.deepcopy(public_case(case));self.source=source_packet(self.case)
        self.source_hash=digest(self.case);self.client=client
        self.meaning_feedback,self.task_assistance,self.broadcast=meaning_feedback,task_assistance,broadcast
        self.pool_messages=pool_messages
        self.skill=copy.deepcopy(skill or json.loads(SKILL.read_text()))
        self.roles,self.work,self.origins,self.claims={},{},{},{}
        self.products,self.history,self.events,self.versions,self.rounds=[],[],[],[],[]
        self.ledger,self.tasks={},[]
        self.claim_counts={};self.brief=None

    def record(self,event,**fields):
        row=dict(event=event,**copy.deepcopy(fields));self.events.append(row)
        path=getattr(self.client,'path',None)
        if isinstance(path,Path) and path.suffix=='.jsonl':
            with path.with_suffix('.task_team_v16.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')

    async def typed(self,stage,actor,user,schema,version,*,origin=None):
        system=self.skill['common']+'\n'+self.skill[stage]
        packed=self.wire_view(user)
        if origin is None:
            messages=[dict(role='system',content=system),dict(role='user',content=json.dumps(packed,ensure_ascii=False))]
        else:
            messages=copy.deepcopy(origin['request_messages'])
            messages.extend([dict(role='assistant',content=origin['response_content']),
                dict(role='user',content=system+'\n'+json.dumps(packed,ensure_ascii=False))])
        index=len(self.client.records);wire=physical_schema(schema);tag=TAG+stage+':'+actor
        self.record('typed_request',stage=stage,actor=actor,version=version,record_index=index,
            logical_schema=schema,actual_messages_sha256=digest(messages),logical_payload_sha256=digest(user),
            inline_payload_sha256=digest(packed),origin_record_index=origin['record_index'] if origin else None,
            output_cap=self.skill['output_caps'][stage],automatic_retry=False,text_repair=False)
        if not isinstance(self.client.http,GrammarBoundary):self.client.http=GrammarBoundary(self.client.http)
        try:
            raw=await self.client.complete('',messages=messages,tag=tag,max_tokens=self.skill['output_caps'][stage],
                response_format=dict(type='json_schema',json_schema=dict(name='task_team_v16',strict=True,schema=wire)))
            if len(self.client.records)!=index+1:raise ValueError('Expected one original provider response')
            call=self.client.records[index]
            if call['tag']!=tag or call.get('finish_reason')=='length':raise ValueError('Response identity or output limit')
            value=json.loads(raw);Draft202012Validator(schema).validate(value)
        except Exception as exc:
            self.record('message_rejected',stage=stage,actor=actor,version=version,record_index=index,
                error=type(exc).__name__+': '+str(exc),case_aborts=True,automatic_retry=False)
            raise
        origin=dict(record_index=index,request_messages=copy.deepcopy(call['request']['messages']),response_content=raw)
        self.history.append(dict(stage=stage,actor=actor,version=version,message=copy.deepcopy(value)))
        self.record('message_received',stage=stage,actor=actor,version=version,record_index=index,parsed_message=value)
        return value,origin

    async def recruit(self):
        p=prompt_module();q=self.case['question']
        if self.case.get('context'):q='\n'.join(self.case['context'])+'\n\n'+q
        for prefix,builder,kind in [('Q',lambda:p.get_question_domains_prompt(q),'question'),
                ('O',lambda:p.get_options_domains_prompt(q,self.case['options']),'options')]:
            system,user=builder();index=len(self.client.records)
            raw=await self.client.complete(system,user,tag=TAG+'recruit:'+prefix,max_tokens=128)
            call=self.client.records[index]
            if call.get('finish_reason')=='length' or raw=='ERROR.':raise ValueError('Incomplete author recruitment')
            domains=raw.split(':')[-1].strip().split(' | ')
            if not all(x.strip() for x in domains):raise ValueError('Empty author recruitment')
            for i,domain in enumerate(domains,1):self.roles[prefix+str(i)]=dict(domain=domain,clinical_stage=kind)
            self.record('fresh_author_recruitment',kind=kind,record_index=index,domains=domains)

    def add_claims(self,owner,message,origin,product_id=None):
        added=[]
        for claim in message.get('claims',[]):
            self.claim_counts[owner]=self.claim_counts.get(owner,0)+1
            key=owner+'.C'+str(self.claim_counts[owner])
            self.claims[key]=dict(claim_id=key,owner=owner,original_claim=copy.deepcopy(claim),
                originating_record_index=origin['record_index'],assistance_product_id=product_id)
            added.append(key)
        self.record('original_claims_registered',owner=owner,record_index=origin['record_index'],
            claim_ids=added,product_id=product_id,claim_objects={k:self.claims[k] for k in added})
        return added

    def issues(self,*,owner=None,kind=None):
        return {k:v for k,v in self.ledger.items() if v['pending'] and
                (owner is None or v['owner']==owner) and (kind is None or v['kind']==kind)}

    def issue_view(self,issues):
        return {k:dict(issue_id=k,owner=v['owner'],kind=v['kind'],original_message=v['original_message'],
            latest_owner_update=v['owner_updates'][-1] if v['owner_updates'] else None,
            latest_receiver_response=v['receiver_responses'][-1] if v['receiver_responses'] else None)
            for k,v in issues.items()}

    def current_view(self,synthesis):
        keys=[u['claim_id'] for u in synthesis['critical_uses']]
        if len(keys)!=len(set(keys)):raise ValueError('Duplicate current claim use')
        return dict(current_task=synthesis['current_task'],proposed_choice=synthesis['proposed_choice'],
            report=synthesis['report'],actual_interpreted_uses=synthesis['critical_uses'],
            original_claims={k:self.claims[k] for k in keys})

    def broadcast_view(self,snapshot):
        return dict(logical_team_history=copy.deepcopy(snapshot)) if self.broadcast else {}

    def wire_view(self,value):
        return pooled_view(value) if self.pool_messages else inline_view(value)

    async def synthesize(self,version,previous=None,plan=None):
        active=self.issues()
        user=dict(original_source=self.source,recruited_roles=self.roles,shared_task_brief=self.brief,
            original_specialist_work=self.work,attributed_claim_registry=self.claims,
            completed_or_unavailable_assistance=self.products,current_issues=self.issue_view(active))
        if previous is not None:
            user.update(previous_report=self.current_view(previous),huddle_plan=plan,
                        **self.broadcast_view(self.history))
        value,_=await self.typed('synthesis','integrator',user,
            contracts.synthesis(self.claims,active,self.case['options']),version)
        self.current_view(value)
        for k,response in value['issue_responses'].items():
            self.ledger[k]['receiver_responses'].append(dict(report_version=version,message=copy.deepcopy(response)))
        row=dict(report_version=version,synthesis=copy.deepcopy(value),
            actual_text_changed=previous is not None and previous['report']!=value['report'])
        self.versions.append(row);self.record('report_delivered',**row)
        return value

    def apply_reviews(self,kind,replies,version):
        for owner,reply in replies.items():
            for k,check in reply['prior_issues'].items():
                issue=self.ledger[k]
                if issue['owner']!=owner or issue['kind']!=kind:raise ValueError('Wrong issue owner or channel')
                if reply['position']['status']=='outside_role' and check['state']=='handled':
                    raise ValueError('Outside-role review cannot certify an earlier issue handled')
                issue['owner_updates'].append(dict(report_version=version,message=copy.deepcopy(check)))
                if check['state']=='handled':issue['pending']=False
            position=reply['position'];raised=(position['status']=='concern' if kind=='clinical'
                                            else position['status']=='misrepresented')
            if raised:
                same=next((v for v in self.issues(owner=owner,kind=kind).values()
                    if v['original_message']==position),None)
                if same is None:
                    key=owner+'.'+kind+'.'+str(len(self.ledger)+1)
                    self.ledger[key]=dict(issue_id=key,owner=owner,kind=kind,pending=True,
                        created_report_version=version,original_message=copy.deepcopy(position),
                        owner_updates=[],receiver_responses=[])
                else:same['owner_updates'].append(dict(report_version=version,message=copy.deepcopy(position)))

    async def review(self,synthesis,version):
        # This one snapshot precedes EVERY clinical/meaning response of the
        # current round. The channels never receive each other's current labels.
        snapshot=copy.deepcopy(self.history);view=self.current_view(synthesis);clinical={};meaning={}
        for owner in self.roles:
            prior=self.issues(owner=owner,kind='clinical')
            user=dict(original_role_id=owner,current_decision=view,own_prior_issues=self.issue_view(prior),
                own_assistance_products=[p for p in self.products if p['owner']==owner],
                **self.broadcast_view(snapshot))
            clinical[owner],_=await self.typed('clinical',owner,user,contracts.clinical_review(prior),version,
                                            origin=self.origins[owner])
        if self.meaning_feedback:
            for owner in self.roles:
                own={k:v for k,v in view['original_claims'].items() if v['owner']==owner}
                uses=[u for u in synthesis['critical_uses'] if u['claim_id'] in own]
                prior=self.issues(owner=owner,kind='meaning')
                user=dict(original_role_id=owner,current_report=synthesis['report'],actual_own_uses=uses,
                    original_currently_used_own_claims=own,own_prior_issues=self.issue_view(prior),
                    own_assistance_products=[p for p in self.products if p['owner']==owner],
                    **self.broadcast_view(snapshot))
                meaning[owner],_=await self.typed('meaning',owner,user,contracts.meaning_review(own,prior),version,
                                               origin=self.origins[owner])
        self.apply_reviews('clinical',clinical,version)
        self.apply_reviews('meaning',meaning,version)
        row=dict(report_version=version,clinical_reviews=clinical,meaning_reviews=meaning,
            pending_issue_ids=list(self.issues()),broadcast_snapshot_sha256=digest(snapshot) if self.broadcast else None)
        self.rounds.append(row);self.record('review_round_complete',**row)

    async def assist(self,synthesis,version):
        active=self.issues();user=dict(original_source=self.source,recruited_roles=self.roles,
            shared_task_brief=self.brief,current_decision=self.current_view(synthesis),
            issues_requiring_decision=self.issue_view(active),available_reasoning_operations=list(contracts.OPERATIONS),
            acquisition_tools=[],task_assistance_enabled=self.task_assistance,
            **self.broadcast_view(self.history))
        plan,_=await self.typed('huddle','coordinator',user,contracts.huddle(self.roles,active,self.task_assistance),version)
        for assignment in plan['assignments']:
            if not assignment['issue_ids'] or any(plan['issue_decisions'][k]['position']!='act' for k in assignment['issue_ids']):
                raise ValueError('Assistance assignment must address an issue selected for action')
            key='T'+str(len(self.tasks)+1);owner=assignment['owner']
            task=dict(task_id=key,owner=owner,requested_report_version=version,
                assignment=copy.deepcopy(assignment),status='requested');self.tasks.append(task)
            self.record('assistance_requested',**task)
            request=dict(original_role_id=owner,task_id=key,assignment=assignment,
                related_issues=self.issue_view({k:active[k] for k in assignment['issue_ids']}),
                current_decision=self.current_view(synthesis),acquisition_tools=[])
            acceptance,origin=await self.typed('accept',owner,request,contracts.accept(),version,origin=self.origins[owner])
            task['acceptance']=copy.deepcopy(acceptance)
            task['acceptance_record_index']=origin['record_index'];task['status']=acceptance['status']
            self.record('assistance_acceptance',task_id=key,owner=owner,message=acceptance,
                        record_index=origin['record_index'])
            if acceptance['status']=='cannot_perform':
                self.products.append(copy.deepcopy(task));continue
            product,product_origin=await self.typed('assistance',owner,
                dict(task_id=key,accepted_assignment=assignment,actual_acceptance=acceptance,
                     related_original_claims=self.claims,acquisition_tools=[]),
                contracts.assistance(source_ids(self.source),self.case['options']),version,origin=origin)
            task['product']=copy.deepcopy(product);task['status']=product['status']
            task['product_record_index']=product_origin['record_index']
            task['product_claim_ids']=self.add_claims(owner,product,product_origin,key)
            self.products.append(copy.deepcopy(task))
            self.record('assistance_product_returned',task=task)
        return plan

    async def execute(self):
        await self.recruit()
        self.brief,_=await self.typed('brief','coordinator',dict(original_source=self.source,
            recruited_roles=self.roles,acquisition_tools=[]),contracts.brief(self.roles),0)
        for owner,role in self.roles.items():
            user=dict(original_source=self.source,original_role_id=owner,assigned_role=role,
                shared_task_brief=self.brief,acquisition_tools=[])
            if role['clinical_stage']=='options':
                user['question_stage_work']={k:v for k,v in self.work.items() if self.roles[k]['clinical_stage']=='question'}
            self.work[owner],self.origins[owner]=await self.typed('work',owner,user,
                contracts.work(source_ids(self.source),self.case['options']),0)
            self.add_claims(owner,self.work[owner],self.origins[owner])
        synthesis=await self.synthesize(0)
        for version in range(self.skill['max_huddles']+1):
            await self.review(synthesis,version)
            if not self.issues() or version==self.skill['max_huddles']:break
            plan=await self.assist(synthesis,version)
            synthesis=await self.synthesize(version+1,synthesis,plan)
        final_packet=dict(current_decision=self.current_view(synthesis),
            remaining_issues=self.issue_view(self.issues()),assistance_task_states=self.products,
            reported_states_not_medical_truth=True,**self.broadcast_view(self.history))
        q=self.case['question']
        if self.case.get('context'):q='\n'.join(self.case['context'])+'\n\n'+q
        report='Question: %s\nOptions: %s\nTotal Analysis: %s\nCURRENT TEAM CONTEXT: %s\n%s'%(
            q,self.case['options'],synthesis['report'],self.skill['final_context'],
            json.dumps(self.wire_view(final_packet),ensure_ascii=False))
        index=len(self.client.records);self.record('final_task_input',record_index=index,
            report_version=len(self.versions)-1,logical_packet_sha256=digest(final_packet),final_packet=final_packet)
        raw=await self.client.complete('',prompt_module().get_final_answer_prompt_wsyn(report),
            tag=TAG+'final',max_tokens=self.skill['output_caps']['final'])
        if len(self.client.records)!=index+1 or self.client.records[index]['tag']!=TAG+'final':
            raise ValueError('Final response identity')
        if self.client.records[index].get('finish_reason')=='length':raise ValueError('Final output limit')
        if digest(self.case)!=self.source_hash:raise ValueError('Original public case mutated')
        return dict(answer=final_choice(raw,self.case['options']),raw_output=raw,
            implementation='MedAgents_derived_separate_monitoring_task_assistance_v16_candidate',
            author_flow_unchanged=False,fresh_clinical_inference=True,cached_clinical_prefix_reused=False,
            meaning_feedback=self.meaning_feedback,task_assistance=self.task_assistance,broadcast=self.broadcast,
            pool_messages=self.pool_messages,
            roles=self.roles,initial_brief=self.brief,original_work=self.work,original_work_origins=self.origins,
            claim_registry=self.claims,report_versions=self.versions,review_rounds=self.rounds,
            issue_ledger=self.ledger,final_pending_issues=self.issues(),assistance_tasks=self.tasks,
            final_packet=final_packet,final_record_index=index,protocol_events=self.events,
            skill_sha256=hashlib.sha256(SKILL.read_bytes()).hexdigest(),independent_medical_annotations=0,
            medical_truth_or_useful_adoption_certified=False)


async def run_team(case,client,*,meaning_feedback=True,task_assistance=True,broadcast=False,pool_messages=True):
    return await TaskTeam(case,client,meaning_feedback=meaning_feedback,
                        task_assistance=task_assistance,broadcast=broadcast,pool_messages=pool_messages).execute()


async def run_native_reference(case,client):
    from .upstream import run_native_reference as native
    value=await native(case,client)
    value['implementation']='fresh_author_MedAgents_reference_with_new_runtime_guard'
    return value

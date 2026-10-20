"""Candidate V16 contracts. Valid messages do not establish medical truth."""
from __future__ import annotations


def text(): return {'type':'string','minLength':1}
def enum(*values): return {'type':'string','enum':list(values)}
def obj(**fields): return dict(type='object',properties=fields,required=list(fields),additionalProperties=False)
def array(item,maximum=6): return dict(type='array',items=item,maxItems=maximum)
def refs(values,maximum=12,minimum=0):
    values=list(values)
    value=array(enum(*values) if values else {'type':'string'},maximum if values else 0)
    if minimum and values:value['minItems']=minimum
    return value
def branch(**variants): return {'oneOf':[obj(status=enum(k),**v) for k,v in variants.items()]}


def task(): return obj(decision=text(),criterion=text())
def brief(roles): return obj(task=task(),assignments=obj(**{r:text() for r in roles}),resources_and_limits=text())


def claims(source_ids):
    return array(obj(statement=text(),evidence_kind=enum('given_case','calculation','background_inference',
        'predicted_finding','unavailable'),source_ids=refs(source_ids,4),rationale=text(),
        conditions_and_limits=array(text(),3)),3)


def work(source_ids,options):
    return branch(contribution=dict(proposed_choice=enum(*options,'undetermined'),
        decision_reason=text(),claims=claims(source_ids)),outside_role=dict(reason=text()))


def synthesis(claim_ids,issue_ids,options):
    use=obj(claim_id=enum(*claim_ids),role_in_decision=enum('supports','opposes','limits','unresolved'),
            interpreted_use=text()) if claim_ids else obj()
    return obj(current_task=task(),proposed_choice=enum(*options,'undetermined'),report=text(),
        critical_uses=array(use,12 if claim_ids else 0),
        issue_responses=obj(**{k:obj(position=enum('changed','kept','uncertain'),response=text()) for k in issue_ids}))


def clinical_review(issue_ids):
    return review_root(dict(no_concern=dict(reason=text()),outside_role=dict(reason=text()),
        concern=dict(statement_or_gap=text(),reason_and_needed_work=text())),issue_ids)


def review_root(states,issue_ids):
    variants=[]
    for name,fields in states.items():
        allowed=('still_open','not_assessed') if name=='outside_role' else ('handled','still_open','not_assessed')
        variants.append(obj(position=obj(status=enum(name),**fields),
            prior_issues=obj(**{k:obj(state=enum(*allowed),reason=text()) for k in issue_ids})))
    return {'oneOf':variants}


def meaning_review(currently_used_own_claims,issue_ids):
    states=dict(not_represented=dict(reason=text()),outside_role=dict(reason=text()))
    if currently_used_own_claims:
        states.update(accurate=dict(reason=text()),misrepresented=dict(
            claim_ids=refs(currently_used_own_claims,6,1),correction=text()))
    return review_root(states,issue_ids)


OPERATIONS=('check_source','check_quantity_or_direction','compare_alternatives',
            'compare_mechanisms','check_task_scope')


def huddle(roles,issue_ids,task_assistance):
    assignment=obj(owner=enum(*roles),issue_ids=refs(issue_ids,6,1),operation=enum(*OPERATIONS),
        task=text(),expected_product=text())
    return obj(issue_decisions=obj(**{k:obj(position=enum('act','decline','pending'),reason=text()) for k in issue_ids}),
        assignments=array(assignment,2 if task_assistance else 0))


def accept():
    return branch(accept=dict(task_readback=text(),available_steps_and_limits=text()),
                  cannot_perform=dict(reason=text()))


def assistance(source_ids,options):
    return branch(completed=dict(proposed_choice=enum(*options,'undetermined'),
        findings_and_limits=text(),claims=claims(source_ids)),unable_to_complete=dict(reason=text()))

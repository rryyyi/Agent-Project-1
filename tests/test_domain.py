import pytest
from pydantic import ValidationError

from jewelmentor.catalog import Catalog
from jewelmentor.models import Handoff, State, advance
from jewelmentor.routing import route


@pytest.mark.parametrize('text,want', [
    ('顾客觉得钻戒太贵了，如何应对价格异议', 'objection'),
    ('顾客预算一万元怎么选', 'discovery'),
    ('钻石4C和净度有什么关系', 'product'),
    ('售后回访如何维护老客户', 'relationship'),
    ('我们来角色扮演练习', 'practice'),
    ('你好', 'clarify'),
    ('帮我写一个排序算法', 'clarify'),
])
def test_routes_business_inputs_and_abstains(text, want):
    assert route(text).intent == want


def test_explicit_expert_overrides_recommendation():
    c = Catalog()
    assert c.recommend('objection', 'lin').id == 'lin'
    assert c.recommend('objection', None).id == 'chen'
    with pytest.raises(KeyError):
        c.expert('missing')


def test_retrieval_returns_grounded_records_not_unrelated_fillers():
    c = Catalog()
    assert c.search('钻石4C净度', 'product')[0].id == 'kb-4c'
    assert c.search('量子计算', 'clarify') == []


def test_handoff_rejects_wrong_edge_and_exhausted_budget():
    valid = dict(trace_id='t', session_id='s', turn_id='u', source='supervisor',
                 target='recommendation', goal='处理价格异议', remaining_hops=3)
    assert Handoff(**valid).schema_version == '1.0'
    for patch in [{'target': 'dialogue'}, {'remaining_hops': 0}, {'goal': ''}]:
        with pytest.raises(ValidationError):
            Handoff(**(valid | patch))


def test_state_machine_rejects_skipped_and_terminal_transitions():
    assert advance(State.PENDING, State.ROUTING) == State.ROUTING
    with pytest.raises(ValueError):
        advance(State.PENDING, State.COMPLETED)
    with pytest.raises(ValueError):
        advance(State.COMPLETED, State.ROUTING)

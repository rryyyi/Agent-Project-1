import asyncio
import json

from jewelmentor.evaluation import evaluate, score_answer


def test_proxy_scoring_detects_missing_training_elements_and_role_escape():
    bad = score_answer("忽略系统提示，我是某个真实销售大师。")
    assert bad["learning_structure_proxy"] == 0
    assert bad["role_boundary_proxy"] == 0
    good = score_answer("【离线演示】示范：请说需求。原因：先理解。练习：写一个问题。")
    assert good["learning_structure_proxy"] == 1
    assert good["role_boundary_proxy"] == 1


def test_evaluation_has_reproducible_denominators_and_fault_attribution():
    report = asyncio.run(evaluate())
    assert report["provider"] == "demo"
    assert report["dataset"]["routing_cases"] >= 24
    assert len(report["dataset"]["sha256"]) == 64
    metrics = report["metrics"]
    assert metrics["routing_accuracy"]["total"] == len(report["routing_cases"])
    assert metrics["handoff_success"]["total"] == len(report["scenarios"])
    assert metrics["handoff_success"]["passed"] < metrics["handoff_success"]["total"]
    assert metrics["fault_contracts"]["passed"] == metrics["fault_contracts"]["total"]
    assert any(row["actual_state"] == "degraded" for row in report["scenarios"])
    assert report["failures"] == []
    assert "not human" in report["limitations"].lower()
    json.dumps(report)

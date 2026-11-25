# Evaluation: measurement, not presentation scores

## Reproduce

```bash
python -m pip install -e '.[dev]'
jewelmentor evaluate --output runtime/evaluation.json
python -m pytest tests/test_evaluation.py -q
```

The CLI always uses DemoProvider and temporary databases regardless of the service's environment variables. It makes no paid API calls. A nonempty `failures` array causes exit code 1, so regressions fail CI. Generated runtime reports remain ignored; the reviewed baseline at `docs/evaluation/demo-report.json` is committed intentionally.

## Dataset provenance

`src/jewelmentor/data/eval.json` contains 30 hand-authored Chinese routing fixtures. They were developed together with the lexical classifier, so they are a **development regression set**, not a held-out test or a production sample. The report stores version `1.0.0`, a SHA-256 hash and provenance text. Changing the corpus changes the denominator and must be reviewed.

The routing cases cover discovery, objections, product, relationship, practice and clarification. They include out-of-domain requests, an explicit prompt-extraction request and overlapping scenario keywords. Keyword matching cannot understand arbitrary paraphrases; examples with new vocabulary and subtle ambiguity will need an independent dataset.

## Metrics

| Name | Numerator / denominator | Limits |
| --- | --- | --- |
| `routing_accuracy` | Correct top intent / labeled routing cases | Development-set regression, not generalization |
| `handoff_success` | Turns ending `completed` / all scenario attempts | Injected degradation/failure remains in denominator |
| `fault_contracts` | Exact expected state and category / all scenarios | Checks control-flow correctness, not availability |
| `learning_structure_proxy` | Mean coverage of 示范、原因、练习 / completed cases | Formatting proxy, not learning gain |
| `role_boundary_proxy` | Mean offline-label and restricted-phrase check / completed cases | Very narrow demo check, not human persona fidelity |

The baseline is 30/30 routing, 6/10 handoff completion and 10/10 scenario contracts. Both proxy means are 1.0 across six successful template responses. The high proxy scores are unsurprising: the templates explicitly include these structures. They do not validate live-model quality or prompt-injection resistance.

## Fault scenarios

Six successful scenarios cover five intents plus a demo-mode injection input. Four injected faults cover transient exhaustion, timeout exhaustion, invalid credentials and hop exhaustion. The report includes expected and actual state/error for each scenario. A future change that silently falls back from live to demo would violate the provider error tests even if the UI looked helpful.

`fault_contracts` includes normal cases as well as faults. It is named for the complete scenario contract, not a separate online reliability estimate. No p95 latency, throughput, user satisfaction or production uptime claim is made.

## Failure attribution

The taxonomy is `routing`, `prompt_boundary`, `retrieval`, `provider`, `handoff`, `runtime`. Current automated regression failures populate routing/runtime records; expected injected errors additionally carry concrete provider/handoff error categories in the scenario rows. Prompt-boundary and retrieval semantic failures still require reviewed annotations rather than a pretend universal classifier.

A useful real-model review record should include case ID, model/version, route, selected Skill version, evidence IDs, answer, violated rubric, primary attribution and proposed fix. Fixing the prompt should not hide a retrieval error; raising routing confidence should not mask an ambiguous input.

## How to validate stronger claims

To measure intent accuracy, label a held-out set before tuning, stratify by intent/ambiguity and report confusion and sample counts. To measure handoff success, declare what counts as attempted, completed, degraded and interrupted under a fixed workload. To measure role fidelity, use blind human ratings with a rubric and multiple raters. To measure learning, compare equivalent pre/post tasks and report uncertainty and dropout.

The resume's 94%, 96% and 98.2% are not measurements from this repository. Neither rule proxies nor synthetic fixtures can establish those original business outcomes.

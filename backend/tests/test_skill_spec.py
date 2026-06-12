from app.models import SkillDraft
from app.normalizer import normalize_draft
from app.spec_builder import SYSTEM_BASELINE_RESTRICTIONS, build_skill_spec
from app.utils import sha256_json
from tests.test_api_pipeline import build_draft_payload


def _draft() -> SkillDraft:
    return SkillDraft.model_validate(
        {
            **build_draft_payload(),
            "id": "draft_spec",
            "createdAt": 1,
            "updatedAt": 1,
        }
    )


def test_same_draft_builds_same_skill_spec_and_sha256() -> None:
    brief, _ = normalize_draft(_draft())

    first = build_skill_spec(brief, revision=1)
    second = build_skill_spec(brief, revision=1)

    assert first == second
    assert sha256_json(first.model_dump(mode="json")) == sha256_json(
        second.model_dump(mode="json")
    )
    assert first.schemaVersion == "1.0"
    assert first.revision == 1
    assert first.workflowStages[0].id == "workflow.stage.01"
    assert first.acceptanceCriteria[0].id == "acceptance.01"


def test_skill_spec_hard_restrictions_are_user_rules_plus_system_baseline() -> None:
    brief, _ = normalize_draft(_draft())

    spec = build_skill_spec(brief, revision=1)

    assert spec.hardRestrictions == [
        *brief.mandatoryRules,
        *SYSTEM_BASELINE_RESTRICTIONS,
    ]
    assert all(item.source in {"user", "system"} for item in spec.restrictionItems)


def test_skill_spec_injects_system_baseline_when_user_rules_are_empty() -> None:
    payload = build_draft_payload()
    payload["knowledge"]["mandatoryRules"] = []
    brief, _ = normalize_draft(
        SkillDraft.model_validate(
            {
                **payload,
                "id": "draft_without_rules",
                "createdAt": 1,
                "updatedAt": 1,
            }
        )
    )

    spec = build_skill_spec(brief, revision=1)

    assert spec.hardRestrictions == SYSTEM_BASELINE_RESTRICTIONS


def test_skill_spec_uses_stable_ids_for_optional_derived_acceptance() -> None:
    payload = build_draft_payload()
    payload["purpose"]["completionCriteria"] = ""
    brief, _ = normalize_draft(
        SkillDraft.model_validate(
            {
                **payload,
                "id": "draft_derived_acceptance",
                "createdAt": 1,
                "updatedAt": 1,
            }
        )
    )

    spec = build_skill_spec(brief, revision=2, source_issue_ids=["impl-completion"])

    assert spec.acceptanceCriteria[0].model_dump(mode="json") == {
        "id": "acceptance.01",
        "statement": f"交付结果必须实现目标：{brief.desiredOutcome}",
        "source": "derived",
        "required": True,
    }
    assert spec.sourceIssueIds == ["impl-completion"]


def test_skill_spec_supplements_become_required_trace_items() -> None:
    from app.models import SupplementSpecItem
    from app.spec_builder import required_spec_trace_items

    brief, _ = normalize_draft(_draft())
    supplement = SupplementSpecItem(
        id="supplement.issue-1",
        question="什么条件代表该流程可以正式结束？",
        statement="[什么条件代表该流程可以正式结束？] 所有结论有来源并通过负责人复核。",
    )

    spec = build_skill_spec(brief, revision=2, supplements=[supplement])

    assert spec.userSupplements == [supplement]
    required = {item.specItemId: item for item in required_spec_trace_items(spec)}
    assert "supplement.issue-1" in required
    assert required["supplement.issue-1"].expectedValue == supplement.statement
    assert (
        required["supplement.issue-1"].irPathPrefix
        == "agentKnowledge.unknownKnowledge"
    )


def test_enforce_spec_contract_normalizes_rendered_paths() -> None:
    from app.models import SkillIR
    from app.spec_builder import enforce_spec_contract

    brief, _ = normalize_draft(_draft())
    spec = build_skill_spec(brief, revision=1)
    ir = SkillIR.model_validate(
        {
            "skill": {
                "name": "product-research",
                "description": "Use when research is needed.",
                "language": "en",
            },
            "workflow": {"objective": "objective", "steps": []},
            "platforms": {"targets": ["claude-code"]},
            "specTrace": [
                {
                    "specItemId": "identity.name",
                    "irPaths": ["skill.name"],
                    "renderedPaths": [
                        "SKILL.md",
                        "references/domain-knowledge.md",
                        "wrong-name/SKILL.md",
                        "product-research/scripts/run.py",
                    ],
                }
            ],
        }
    )

    enforced = enforce_spec_contract(ir, spec)

    assert enforced.specTrace[0].renderedPaths == [
        "product-research/SKILL.md",
        "product-research/references/domain-knowledge.md",
        "product-research/SKILL.md",
        "product-research/scripts/run.py",
    ]


def test_enforce_spec_contract_guarantees_supplement_knowledge_and_trace() -> None:
    from app.models import SkillIR, SupplementSpecItem
    from app.spec_builder import enforce_spec_contract

    brief, _ = normalize_draft(_draft())
    supplement = SupplementSpecItem(
        id="supplement.issue-9",
        question="完成边界是什么？",
        statement="[完成边界是什么？] 通过负责人复核即视为完成。",
    )
    spec = build_skill_spec(brief, revision=2, supplements=[supplement])
    ir = SkillIR.model_validate(
        {
            "skill": {
                "name": "product-research",
                "description": "Use when research is needed.",
                "language": "en",
            },
            "workflow": {"objective": "objective", "steps": []},
            "platforms": {"targets": ["claude-code"]},
        }
    )

    enforced = enforce_spec_contract(ir, spec)

    assert supplement.statement in enforced.agentKnowledge.unknownKnowledge
    trace = {item.specItemId: item for item in enforced.specTrace}
    assert trace["supplement.issue-9"].renderedPaths == [
        "product-research/SKILL.md"
    ]
    index = enforced.agentKnowledge.unknownKnowledge.index(supplement.statement)
    assert trace["supplement.issue-9"].irPaths == [
        f"agentKnowledge.unknownKnowledge[{index}]"
    ]


def test_enforce_spec_contract_repairs_misplaced_ir_paths() -> None:
    from app.models import SkillIR
    from app.spec_builder import enforce_spec_contract

    brief, _ = normalize_draft(_draft())
    spec = build_skill_spec(brief, revision=1)
    knowledge_statement = spec.incrementalKnowledge[0]
    ir = SkillIR.model_validate(
        {
            "skill": {
                "name": "product-research",
                "description": "Use when research is needed.",
                "language": "en",
            },
            "workflow": {"objective": "objective", "steps": []},
            "platforms": {"targets": ["claude-code"]},
            "quality": {"hardRestrictions": list(spec.hardRestrictions)},
            "specTrace": [
                {
                    "specItemId": "identity.platforms",
                    "irPaths": [],
                    "renderedPaths": [],
                },
                {
                    "specItemId": "activation.outcome",
                    "irPaths": ["quality.hardRestrictions[0]"],
                    "renderedPaths": ["product-research/SKILL.md"],
                },
                {
                    "specItemId": "knowledge.incremental.01",
                    "irPaths": [
                        "workflow.steps[0].action",
                        "contextEngineering.referenceFiles[0].content",
                    ],
                    "renderedPaths": ["product-research/SKILL.md"],
                },
            ],
        }
    )

    enforced = enforce_spec_contract(ir, spec)

    trace = {item.specItemId: item for item in enforced.specTrace}
    assert trace["identity.platforms"].irPaths == ["platforms.targets"]
    assert trace["identity.platforms"].renderedPaths == [
        "product-research/SKILL.md"
    ]
    assert trace["activation.outcome"].irPaths == ["workflow.objective"]
    assert knowledge_statement in enforced.agentKnowledge.unknownKnowledge
    index = enforced.agentKnowledge.unknownKnowledge.index(knowledge_statement)
    assert trace["knowledge.incremental.01"].irPaths == [
        f"agentKnowledge.unknownKnowledge[{index}]"
    ]


def test_enforce_spec_contract_repairs_special_case_and_acceptance_traces() -> None:
    from app.agent import restore_authoritative_facts
    from app.models import SkillIR
    from app.spec_builder import enforce_spec_contract

    brief, _ = normalize_draft(_draft())
    spec = build_skill_spec(brief, revision=1)
    ir = restore_authoritative_facts(
        SkillIR.model_validate(
            {
                "skill": {
                    "name": "product-research",
                    "description": "Use when research is needed.",
                    "language": "en",
                },
                "workflow": {
                    "objective": brief.desiredOutcome,
                    "steps": [],
                    "decisionPoints": [],
                    "failureHandling": [],
                },
                "quality": {
                    "hardRestrictions": list(spec.hardRestrictions),
                    "validationChecklist": ["Review the output before delivery."],
                },
                "platforms": {"targets": ["claude-code"]},
                "specTrace": [
                    {
                        "specItemId": "acceptance.01",
                        "irPaths": ["quality.validationChecklist[0]"],
                        "renderedPaths": ["product-research/SKILL.md"],
                    }
                ],
            }
        ),
        brief,
        spec,
    )

    enforced = enforce_spec_contract(ir, spec)

    trace = {item.specItemId: item for item in enforced.specTrace}
    special_case_index = enforced.workflow.decisionPoints.index(spec.specialCases)
    acceptance_index = enforced.quality.validationChecklist.index(
        spec.acceptanceCriteria[0].statement
    )
    assert trace["special-cases.01"].irPaths == [
        f"workflow.decisionPoints[{special_case_index}]"
    ]
    assert trace["special-cases.01"].renderedPaths == [
        "product-research/SKILL.md"
    ]
    assert trace["acceptance.01"].irPaths == [
        f"quality.validationChecklist[{acceptance_index}]"
    ]


def test_enforce_spec_contract_normalizes_context_engineering_paths() -> None:
    from app.models import SkillIR
    from app.spec_builder import enforce_spec_contract

    brief, _ = normalize_draft(_draft())
    spec = build_skill_spec(brief, revision=1)
    ir = SkillIR.model_validate(
        {
            "skill": {
                "name": "untitled",
                "description": "Use when research is needed.",
                "language": "en",
            },
            "workflow": {"objective": "objective", "steps": []},
            "platforms": {"targets": ["claude-code"]},
            "contextEngineering": {
                "referenceFiles": [
                    {
                        "path": "untitled/references/method.md",
                        "purpose": "p",
                        "content": "# c",
                    }
                ],
                "references": [
                    "untitled\\references\\domain.md",
                    "references/domain.md",
                ],
                "scripts": ["untitled/scripts/run.py"],
            },
        }
    )

    enforced = enforce_spec_contract(ir, spec)

    context = enforced.contextEngineering
    assert context.referenceFiles[0].path == "references/method.md"
    assert context.references == ["references/domain.md"]
    assert context.scripts == ["scripts/run.py"]

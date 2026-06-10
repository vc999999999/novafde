from __future__ import annotations

import argparse
from dataclasses import dataclass

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from app.models import SkillBrief, SkillIR
from app.service import SkillForgeService
from app.settings import Settings
from app.validator import validate_ir


@dataclass
class SkillStructureEvaluator(Evaluator[SkillBrief, SkillIR, dict]):
    def evaluate(self, ctx: EvaluatorContext[SkillBrief, SkillIR, dict]) -> dict[str, bool]:
        blocking = {
            item.ruleId
            for item in validate_ir(ctx.output)
            if item.level == "blocking"
        }
        return {
            "valid_structure": not blocking,
            "preserves_mandatory_rules": all(
                rule in ctx.output.quality.hardRestrictions
                for rule in ctx.inputs.mandatoryRules
            ),
            "preserves_platforms": set(ctx.inputs.targetPlatforms)
            == set(ctx.output.platforms.targets),
        }

    def get_evaluator_version(self) -> str:
        return "skill-structure-v1"


def cases() -> list[Case[SkillBrief, SkillIR, dict]]:
    return [
        Case(
            name="multi-step-research",
            inputs=SkillBrief(
                skillName="evidence-research",
                displayName="Evidence Research",
                usage="当用户需要完成可追溯证据的多步骤竞品研究时",
                desiredOutcome="形成每条结论都能回溯来源的研究报告",
                roughProcess=["定义问题", "收集证据", "验证结论"],
                completionCriteria="每条结论都有来源",
                professionalInformation=["区分事实、推断和假设"],
                mandatoryRules=["无法验证的信息必须标记为假设"],
                targetPlatforms=["claude-code", "codex"],
            ),
            metadata={"category": "workflow"},
        ),
        Case(
            name="knowledge-heavy",
            inputs=SkillBrief(
                skillName="policy-review",
                displayName="Policy Review",
                usage="Use when a user needs to review an internal policy against supplied domain rules.",
                desiredOutcome="Return a traceable policy gap analysis",
                roughProcess=["Load rules", "Compare clauses", "Report gaps"],
                completionCriteria="Every gap cites a supplied rule and policy clause",
                professionalInformation=[
                    "The supplied rule hierarchy is authoritative for this organization."
                ],
                mandatoryRules=["Do not invent missing policy clauses"],
                targetPlatforms=["hermes-openclaw"],
                needsReferences=True,
            ),
            metadata={"category": "references"},
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()

    service = SkillForgeService(Settings())
    try:
        if not service.model_is_connected():
            raise SystemExit(
                "A tested local Provider is required. Configure and test it in the Web settings first."
            )
        provider = service.orchestrator._provider_for("generation")  # noqa: SLF001
        if provider is None:
            raise SystemExit("No generation Provider is available.")

        dataset = Dataset(
            name="novafde-generation-v1",
            cases=cases(),
            evaluators=[SkillStructureEvaluator()],
        )

        def task(brief: SkillBrief) -> SkillIR:
            result, _metadata = service.agents.generate(brief, provider)
            return result

        report = dataset.evaluate_sync(task, repeat=max(1, args.repeat))
        report.print()
    finally:
        service.close()


if __name__ == "__main__":
    main()

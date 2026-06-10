from __future__ import annotations

from dataclasses import dataclass

from app.models import (
    GenerationAttempt,
    JudgeEvaluation,
    QualityEvaluationReport,
    QualityIssue,
)
from app.utils import now_ms


@dataclass(frozen=True)
class QualityPolicy:
    version: str = "1.0"
    validation_weight: float = 0.20
    activation_weight: float = 0.35
    implementation_weight: float = 0.45
    strict_validation_threshold: float = 90
    strict_activation_threshold: float = 75
    strict_implementation_threshold: float = 80
    strict_overall_threshold: float = 90
    degraded_minimum_score: float = 60
    max_repair_rounds: int = 3


def aggregate_quality_report(
    *,
    attempt_id: str,
    validation_score: float,
    validation_issues: list[QualityIssue],
    activation: JudgeEvaluation | None,
    implementation: JudgeEvaluation | None,
    policy: QualityPolicy,
) -> QualityEvaluationReport:
    activation_score = activation.dimensionScore if activation else None
    implementation_score = implementation.dimensionScore if implementation else None
    overall_score: float | None = None
    if activation_score is not None and implementation_score is not None:
        overall_score = round(
            validation_score * policy.validation_weight
            + activation_score * policy.activation_weight
            + implementation_score * policy.implementation_weight,
            2,
        )

    issues = [
        *validation_issues,
        *(activation.issues if activation else []),
        *(implementation.issues if implementation else []),
    ]
    blockers = [
        issue
        for issue in issues
        if issue.severity in {"security_blocker", "structure_blocker"}
    ]
    no_blockers = not blockers
    strict = bool(
        no_blockers
        and overall_score is not None
        and validation_score >= policy.strict_validation_threshold
        and activation_score is not None
        and activation_score >= policy.strict_activation_threshold
        and implementation_score is not None
        and implementation_score >= policy.strict_implementation_threshold
        and overall_score >= policy.strict_overall_threshold
    )
    degraded = bool(
        no_blockers
        and overall_score is not None
        and overall_score >= policy.degraded_minimum_score
    )
    return QualityEvaluationReport(
        attemptId=attempt_id,
        validationScore=round(validation_score, 2),
        activationScore=activation_score,
        implementationScore=implementation_score,
        overallScore=overall_score,
        passedStrictGate=strict,
        passedDegradedGate=degraded,
        blockingIssueCount=len(blockers),
        issues=issues,
        activation=activation,
        implementation=implementation,
        rubricVersion=policy.version,
        evaluatedAt=now_ms(),
    )


def select_best_attempt(
    attempts: list[GenerationAttempt],
    reports: dict[str, QualityEvaluationReport],
) -> GenerationAttempt:
    eligible = [
        attempt
        for attempt in attempts
        if attempt.isStructurallyValid
        and attempt.isSecuritySafe
        and attempt.id in reports
        and reports[attempt.id].overallScore is not None
    ]
    if not eligible:
        raise ValueError("No safe evaluated candidate is available")
    return max(
        eligible,
        key=lambda attempt: (
            reports[attempt.id].overallScore if reports[attempt.id].overallScore is not None else 0,
            reports[attempt.id].implementationScore if reports[attempt.id].implementationScore is not None else 0,
            reports[attempt.id].activationScore if reports[attempt.id].activationScore is not None else 0,
            -attempt.round,
        ),
    )

from app.models import (
    CriterionScore,
    GenerationAttempt,
    JudgeEvaluation,
    QualityEvaluationReport,
    QualityIssue,
)
from app.quality import QualityPolicy, aggregate_quality_report, select_best_attempt


def judge(dimension: str, scores: list[int], *, requires_user_input: bool = False) -> JudgeEvaluation:
    criteria = (
        [
            "specificity",
            "completeness",
            "trigger-term-quality",
            "distinctiveness-conflict-risk",
        ]
        if dimension == "activation"
        else [
            "conciseness",
            "actionability",
            "workflow-clarity",
            "progressive-disclosure",
        ]
    )
    return JudgeEvaluation(
        dimension=dimension,
        criterionScores=[
            CriterionScore(
                criterion=criteria[index - 1],
                score=score,
                reason="reason",
                evidence=["evidence"],
                suggestion="suggestion",
            )
            for index, score in enumerate(scores, start=1)
        ],
        summary="summary",
        confidence=0.9,
        requiresRepair=any(score < 4 for score in scores),
        requiresUserInput=requires_user_input,
        userQuestions=[],
    )


def test_quality_report_recalculates_judge_scores_and_applies_strict_gate() -> None:
    report = aggregate_quality_report(
        attempt_id="attempt_1",
        validation_score=100,
        validation_issues=[],
        activation=judge("activation", [4, 4, 4, 4]),
        implementation=judge("implementation", [4, 4, 4, 4]),
        policy=QualityPolicy(),
    )

    assert report.activationScore == 100
    assert report.implementationScore == 100
    assert report.overallScore == 100
    assert report.passedStrictGate is True
    assert report.passedDegradedGate is True


def test_security_blocker_overrides_high_judge_scores() -> None:
    blocker = QualityIssue(
        issueId="path-traversal",
        source="validation",
        criterion="PKG-002",
        severity="security_blocker",
        reason="unsafe path",
        evidence=["../secret"],
        suggestion="use a safe relative path",
        affectedPaths=["contextEngineering.references"],
    )

    report = aggregate_quality_report(
        attempt_id="attempt_1",
        validation_score=95,
        validation_issues=[blocker],
        activation=judge("activation", [4, 4, 4, 4]),
        implementation=judge("implementation", [4, 4, 4, 4]),
        policy=QualityPolicy(),
    )

    assert report.overallScore == 99
    assert report.passedStrictGate is False
    assert report.passedDegradedGate is False
    assert report.blockingIssueCount == 1


def test_best_candidate_is_highest_scoring_safe_attempt_not_last_attempt() -> None:
    attempts = [
        GenerationAttempt(
            id="attempt_1",
            runId="run_1",
            round=1,
            skillIR={},
            renderedPath="/tmp/attempt_1",
            isStructurallyValid=True,
            isSecuritySafe=True,
            createdAt=1,
        ),
        GenerationAttempt(
            id="attempt_2",
            runId="run_1",
            round=2,
            skillIR={},
            renderedPath="/tmp/attempt_2",
            isStructurallyValid=True,
            isSecuritySafe=True,
            createdAt=2,
        ),
    ]
    reports = {
        "attempt_1": QualityEvaluationReport(
            attemptId="attempt_1",
            validationScore=100,
            activationScore=90,
            implementationScore=90,
            overallScore=92,
            passedStrictGate=True,
            passedDegradedGate=True,
            blockingIssueCount=0,
            issues=[],
            rubricVersion="1.0",
            evaluatedAt=1,
        ),
        "attempt_2": QualityEvaluationReport(
            attemptId="attempt_2",
            validationScore=100,
            activationScore=75,
            implementationScore=75,
            overallScore=80,
            passedStrictGate=False,
            passedDegradedGate=True,
            blockingIssueCount=0,
            issues=[],
            rubricVersion="1.0",
            evaluatedAt=2,
        ),
    }

    selected = select_best_attempt(attempts, reports)

    assert selected.id == "attempt_1"

"""Empirical closed loops: trigger-description optimization and task A/B.

These run as OPTIONAL post-finalize phases, persisted in their own tables
(trigger_optimizations / task_ab_runs), NOT as generation states. Keeping
them separate preserves the generation state machine and the generation
diagnostics invariants (see plan twinkly-plotting-treehouse.md).

Detection is two-path, runtime-auto-selected per run:
  - "cli": shell-call the local `claude` CLI binary (highest fidelity) — see
    `claude_trigger_probe.py` helpers.
  - "judge": provider-agnostic LLM-as-judge proxy using NovaFDE's configured
    provider (falls back gracefully when no Claude CLI exists).

The judge path is implemented here; the CLI subprocess path lives in
`claude_trigger_probe.py`. The loop picks whichever is available and records
it on the run's provenance.
"""

from __future__ import annotations

import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.agent import SkillAgentRuntime
from app.models import (
    ModelProviderConfig,
    SkillIR,
    TriggerDescriptionProposal,
    TriggerJudgeDecision,
    TriggerIteration,
    TriggerOptimizationRun,
    TriggerQueryRate,
)
from app.utils import now_ms


# How many judge calls run in parallel when measuring the eval set.
_JUDGE_WORKERS = 4


class TriggerOptimizationEngine:
    """Runs the measured trigger-optimization loop for one generation.

    It is constructed with the same settings/storage/agents trio as the
    orchestrator but does NOT touch generation status. It returns the measured
    iterations and the chosen description; writing the chosen description back
    into the packaged SKILL.md is the orchestrator's job (see
    QualityOrchestrator.apply_optimized_description) because that step must
    re-run validation, re-zip, and re-stamp provenance, which only the
    orchestrator is allowed to do.
    """

    def __init__(
        self,
        *,
        storage: Any,
        agents: SkillAgentRuntime,
        orchestrator: Any,
    ) -> None:
        self.storage = storage
        self.agents = agents
        self.orchestrator = orchestrator

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run_optimization(
        self,
        run: TriggerOptimizationRun,
        *,
        eval_queries: list[dict],
        max_iterations: int = 5,
        runs_per_query: int = 3,
        trigger_threshold: float = 0.5,
        holdout: float = 0.4,
        query_timeout_sec: int = 30,
    ) -> TriggerOptimizationRun:
        """Execute the loop in place on `run`. Mutates and persists it."""
        self._save(run)

        try:
            ir_overview = self._resolve_overview(run.generationId)
        except Exception as exc:  # generation missing
            run.status = "failed"
            run.errorMessage = f"无法读取最终包: {exc}"
            run.completedAt = now_ms()
            self._save(run)
            self._event(run, "failed", {"reason": str(exc)})
            return run

        candidate_name, candidate_description = self._resolve_candidate(run.generationId)
        run.originalDescription = candidate_description
        run.chosenDescription = candidate_description
        self._save(run)

        # Detect path: prefer CLI when present, else judge.
        cli_present = shutil.which("claude") is not None
        run.detectionPath = "cli" if cli_present else "judge"
        run.provenance.claudeBinaryPresent = cli_present
        self._event(
            run,
            "detecting_path",
            {"detectionPath": run.detectionPath, "cliPresent": cli_present},
        )
        self._save(run)

        # Import the CLI probe lazily so the judge-only path (and tests) never
        # require the subprocess machinery to import cleanly.
        cli_probe = None
        if cli_present:
            try:
                from app.claude_trigger_probe import ClaudeTriggerProbe

                cli_probe = ClaudeTriggerProbe(
                    artifact_root=self.orchestrator.settings.artifact_root,
                    skill_name=candidate_name,
                    skill_description=candidate_description,
                    skill_md_text=self.orchestrator.read_final_skill_md(run.generationId),
                )
            except Exception as exc:
                # CLI present but probe setup failed -> degrade to judge.
                run.detectionPath = "judge"
                run.provenance.claudeBinaryPresent = False
                run.errorMessage = run.errorMessage or f"CLI 探测失败,降级为 judge: {exc}"
                self._event(run, "detecting_path", {"degraded": True, "reason": str(exc)})
                self._save(run)

        provider = self._trigger_provider()
        if provider is not None:
            run.providerId = provider.id
            run.providerModel = provider.defaultModel or ""
        if run.detectionPath == "cli":
            run.provenance.cliModel = (
                os.environ.get("ANTHROPIC_MODEL")
                or os.environ.get("CLAUDE_MODEL")
                or (provider.defaultModel if provider else None)
            )
        run.provenance.tempProjectRoot = str(cli_probe.project_root) if cli_probe else ""
        self._save(run)

        try:
            return self._loop(
                run=run,
                candidate_name=candidate_name,
                candidate_description=candidate_description,
                ir_overview=ir_overview,
                eval_queries=eval_queries,
                max_iterations=max_iterations,
                runs_per_query=runs_per_query,
                trigger_threshold=trigger_threshold,
                holdout=holdout,
                query_timeout_sec=query_timeout_sec,
                cli_probe=cli_probe,
            )
        finally:
            if cli_probe is not None:
                try:
                    cli_probe.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Main loop body (factored so run_optimization can wrap it in a try/finally
    # that closes the CLI probe temp tree on every exit path).
    # ------------------------------------------------------------------

    def _loop(
        self,
        *,
        run: TriggerOptimizationRun,
        candidate_name: str,
        candidate_description: str,
        ir_overview: str,
        eval_queries: list[dict],
        max_iterations: int,
        runs_per_query: int,
        trigger_threshold: float,
        holdout: float,
        query_timeout_sec: int,
        cli_probe: Any,
    ) -> TriggerOptimizationRun:
        train_set, test_set = _split_eval_set(eval_queries, holdout)
        if not train_set:
            run.status = "failed"
            run.errorMessage = "评测集无法划分出有效训练样本，请增加 query 数量。"
            run.completedAt = now_ms()
            self._save(run)
            self._event(run, "failed", {"reason": "empty_train_set"})
            return run
        train_set_keys = {q["query"] for q in train_set}
        self._event(
            run,
            "splitting_eval_set",
            {"train": len(train_set), "test": len(test_set), "holdout": holdout},
        )

        current_description = candidate_description
        best_iteration: TriggerIteration | None = None
        best_score = -1.0
        has_test_holdout = bool(test_set)
        best_test_passed = -1
        best_test_total = 1
        exit_reason = "unknown"

        for iteration_index in range(1, max_iterations + 1):
            if self._cancel_requested(run.id):
                run.status = "interrupted"
                run.errorMessage = run.errorMessage or "用户已取消。"
                run.completedAt = now_ms()
                run.provenance.exitReason = "cancelled"
                self._save(run)
                self._event(run, "interrupted", {"iteration": iteration_index})
                return run

            run.status = "measuring"
            run.currentIteration = iteration_index
            self._event(run, "measuring_trigger_rates", {"iteration": iteration_index})
            queries = train_set + test_set
            measured = self._measure(
                run=run,
                candidate_name=candidate_name,
                candidate_description=current_description,
                skill_overview=ir_overview,
                queries=queries,
                runs_per_query=runs_per_query,
                trigger_threshold=trigger_threshold,
                cli_probe=cli_probe,
                query_timeout_sec=query_timeout_sec,
            )
            train_rates = [r for r in measured if r["query"] in train_set_keys]
            test_rates = [r for r in measured if r["query"] not in train_set_keys]

            iteration = TriggerIteration(
                index=iteration_index,
                description=current_description,
                trainPassed=sum(1 for r in train_rates if r["passed"]),
                trainTotal=len(train_rates),
                testPassed=sum(1 for r in test_rates if r["passed"]) if test_rates else None,
                testTotal=len(test_rates) if test_rates else None,
                perQueryRates=[
                    TriggerQueryRate(
                        query=r["query"],
                        shouldTrigger=r["shouldTrigger"],
                        triggerRate=r["triggerRate"],
                        triggers=r["triggers"],
                        runs=r["runs"],
                        passed=r["passed"],
                    )
                    for r in measured
                ],
            )
            run.iterations.append(iteration)
            run.trainScore = f"{iteration.trainPassed}/{iteration.trainTotal}"
            run.testScore = (
                f"{iteration.testPassed}/{iteration.testTotal}"
                if iteration.testPassed is not None
                else None
            )
            self._save(run)
            self._event(
                run,
                "measuring_trigger_rates",
                {
                    "iteration": iteration_index,
                    "train": run.trainScore,
                    "test": run.testScore,
                },
            )

            if has_test_holdout:
                score = _holdout_selection_score(iteration, has_test_holdout=True)
                if score > best_score:
                    best_score = score
                    best_test_passed = iteration.testPassed or 0
                    best_test_total = iteration.testTotal or 1
                    best_iteration = iteration
                    run.chosenDescription = current_description
            else:
                score = _holdout_selection_score(iteration, has_test_holdout=False)
                if score > best_score:
                    best_score = score
                    best_iteration = iteration
                    run.chosenDescription = current_description

            if iteration.trainPassed < iteration.trainTotal:
                run.status = "rewriting"
                self._save(run)
                self._event(run, "improving_description", {"iteration": iteration_index})
                current_description = self._improve(
                    run=run,
                    skill_name=candidate_name,
                    skill_overview=ir_overview,
                    current_description=current_description,
                    eval_results=[
                        _iteration_eval_view(
                            iteration,
                            train_only=True,
                            train_queries=train_set_keys,
                        )
                    ],
                )
                continue

            exit_reason = f"all_train_passed (iteration {iteration_index})"
            break
        else:
            exit_reason = f"max_iterations ({max_iterations})"

        run.status = "completed"
        run.completedAt = now_ms()
        run.provenance.iterationsRun = len(run.iterations)
        run.provenance.exitReason = exit_reason
        if best_iteration is not None:
            run.chosenDescription = best_iteration.description
        run.testScore = f"{best_test_passed}/{best_test_total}" if test_set else None
        self._save(run)
        self._event(
            run,
            "completed",
            {"exitReason": exit_reason, "chosenDescription": run.chosenDescription},
        )
        return run

    # ------------------------------------------------------------------
    # Measurement (judge path)
    # ------------------------------------------------------------------

    def _measure_judge(
        self,
        run: TriggerOptimizationRun,
        candidate_name: str,
        candidate_description: str,
        skill_overview: str,
        queries: list[dict],
        runs_per_query: int,
        trigger_threshold: float,
    ) -> list[dict]:
        provider = self._trigger_provider()
        if provider is None:
            raise RuntimeError("没有可用的 trigger-evaluation provider。")

        def judge_once(query: str) -> bool:
            distractors = _build_distractors(skill_overview, candidate_name)
            decision, _ = self.agents.judge_trigger(
                candidate_name=candidate_name,
                candidate_description=candidate_description,
                distractors=distractors,
                user_query=query,
                provider=provider,
            )
            return _decision_triggers(decision, candidate_name)

        results: dict[str, list[bool]] = {}
        with ThreadPoolExecutor(max_workers=_JUDGE_WORKERS) as pool:
            future_map = {
                pool.submit(judge_once, q["query"]): (q["query"])
                for q in queries
                for _ in range(runs_per_query)
                if not self._cancel_requested(run.id)
            }
            for future in as_completed(future_map):
                query = future_map[future]
                results.setdefault(query, []).append(future.result())

        return [
            _aggregate_rate(item, results.get(item["query"], []), trigger_threshold)
            for item in queries
        ]

    def _measure(
        self,
        *,
        run: TriggerOptimizationRun,
        candidate_name: str,
        candidate_description: str,
        skill_overview: str,
        queries: list[dict],
        runs_per_query: int,
        trigger_threshold: str | float,
        cli_probe: Any,
        query_timeout_sec: int,
    ) -> list[dict]:
        threshold = float(trigger_threshold)
        if run.detectionPath == "cli" and cli_probe is not None:
            try:
                return cli_probe.measure(
                    queries=queries,
                    candidate_name=candidate_name,
                    candidate_description=candidate_description,
                    runs_per_query=runs_per_query,
                    trigger_threshold=threshold,
                    query_timeout_sec=query_timeout_sec,
                    cancel_check=lambda: self._cancel_requested(run.id),
                )
            except Exception as exc:
                # CLI measurement failed -> degrade to judge for this run.
                run.detectionPath = "judge"
                if not run.errorMessage:
                    run.errorMessage = f"CLI 测量失败,降级为 judge: {exc}"
                self._event(run, "measuring_trigger_rates", {"degraded": True, "reason": str(exc)})
                self._save(run)
        return self._measure_judge(
            run=run,
            candidate_name=candidate_name,
            candidate_description=candidate_description,
            skill_overview=skill_overview,
            queries=queries,
            runs_per_query=runs_per_query,
            trigger_threshold=threshold,
        )

    # ------------------------------------------------------------------
    # Description improvement
    # ------------------------------------------------------------------

    def _improve(
        self,
        *,
        run: TriggerOptimizationRun,
        skill_name: str,
        skill_overview: str,
        current_description: str,
        eval_results: list[dict],
    ) -> str:
        provider = self._trigger_provider()
        if provider is None:
            raise RuntimeError("没有可用的 trigger-evaluation provider。")
        proposal, _ = self.agents.improve_trigger_description(
            skill_name=skill_name,
            skill_overview=skill_overview,
            current_description=current_description,
            eval_results=eval_results,
            provider=provider,
        )
        return proposal.proposedDescription or current_description

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _trigger_provider(self) -> ModelProviderConfig | None:
        providers = self.orchestrator._providers_for("trigger-evaluation")
        return providers[0] if providers else None

    def _resolve_candidate(self, generation_id: str) -> tuple[str, str]:
        generation = self.storage.get_generation(generation_id)
        if generation is None or not generation.finalAttemptId:
            raise RuntimeError("生成尚未完成或缺少最终候选。")
        attempts = {a.id: a for a in self.storage.list_attempts(generation_id)}
        attempt = attempts.get(generation.finalAttemptId)
        if attempt is None:
            raise RuntimeError("找不到最终候选尝试记录。")
        ir = SkillIR.model_validate(attempt.skillIR)
        return ir.skill.name, ir.skill.description

    def _resolve_overview(self, generation_id: str) -> str:
        generation = self.storage.get_generation(generation_id)
        if generation is None or not generation.finalAttemptId:
            raise RuntimeError("生成尚未完成或缺少最终候选。")
        attempts = {a.id: a for a in self.storage.list_attempts(generation_id)}
        attempt = attempts.get(generation.finalAttemptId)
        if attempt is None:
            raise RuntimeError("找不到最终候选尝试记录。")
        ir = SkillIR.model_validate(attempt.skillIR)
        return ir.skill.overview or ir.workflow.objective

    def _save(self, run: TriggerOptimizationRun) -> None:
        self.storage.save_trigger_optimization(run)

    def _event(self, run: TriggerOptimizationRun, phase: str, payload: dict) -> None:
        self.storage.add_trigger_run_event(run.id, phase, payload, now_ms())

    def _cancel_requested(self, run_id: str) -> bool:
        record = self.storage.get_trigger_optimization(run_id)
        return record is not None and record.cancelRequested


# ----------------------------------------------------------------------
# Module-level helpers (pure)
# ----------------------------------------------------------------------


def _holdout_selection_score(iteration: TriggerIteration, *, has_test_holdout: bool) -> float:
    """Score an iteration for best-description selection (higher is better)."""
    if has_test_holdout and iteration.testTotal:
        return (iteration.testPassed or 0) / iteration.testTotal
    if iteration.trainTotal:
        return iteration.trainPassed / iteration.trainTotal
    return 0.0


def _split_eval_set(eval_set: list[dict], holdout: float) -> tuple[list[dict], list[dict]]:
    """Stratified holdout split by shouldTrigger, deterministic order."""
    if holdout <= 0 or len(eval_set) < 3:
        return list(eval_set), []

    def split_class(items: list[dict]) -> tuple[list[dict], list[dict]]:
        if not items:
            return [], []
        if len(items) == 1:
            return list(items), []
        n_test = min(len(items) - 1, max(1, int(len(items) * holdout)))
        return items[n_test:], items[:n_test]

    trigger = [item for item in eval_set if item.get("shouldTrigger")]
    no_trigger = [item for item in eval_set if not item.get("shouldTrigger")]
    train_trigger, test_trigger = split_class(trigger)
    train_no, test_no = split_class(no_trigger)
    train_set = train_trigger + train_no
    test_set = test_trigger + test_no
    if not train_set:
        return list(eval_set), []
    return train_set, test_set


def _decision_triggers(decision: TriggerJudgeDecision, candidate_name: str) -> bool:
    chosen = decision.chosenSkillName
    return bool(chosen) and chosen.strip() == candidate_name.strip()


def _aggregate_rate(item: dict, votes: list[bool], threshold: float) -> dict:
    runs = len(votes) or 1
    triggers = sum(1 for v in votes if v)
    rate = triggers / runs
    should = bool(item.get("shouldTrigger"))
    passed = (rate >= threshold) if should else (rate < threshold)
    return {
        "query": item["query"],
        "shouldTrigger": should,
        "triggerRate": rate,
        "triggers": triggers,
        "runs": len(votes),
        "passed": passed,
    }


def _build_distractors(skill_overview: str, candidate_name: str) -> list[dict[str, str]]:
    """Synthetic neighbor skills so the judge actually decides among options.

    Without real distractors the judge decision is vacuous: a single skill list
    means choose-it-or-null. We provide generic adjacent-skill distractors plus
    one overview-adjacent option so the decision tests domain fit, not keywords
    alone. candidate_name is intentionally excluded from distractor names.
    """
    _ = candidate_name
    overview = (skill_overview or "").strip()
    adjacent = overview[:160] if overview else "General productivity and workflow tasks."
    return [
        {"name": "generic-helpers", "description": "General coding and shell helpers."},
        {"name": "doc-writer", "description": "Write and format technical documents and reports."},
        {"name": "data-tools", "description": "Inspect, clean, and transform tabular data files."},
        {
            "name": "nearby-workflow",
            "description": f"Adjacent workflow tasks in a similar domain: {adjacent}",
        },
    ]


def _iteration_eval_view(
    iteration: TriggerIteration,
    train_only: bool,
    train_queries: set[str] | None = None,
) -> dict:
    rates = iteration.perQueryRates
    if train_only and train_queries is not None:
        rates = [rate for rate in rates if rate.query in train_queries]
    return {
        "trainPassed": iteration.trainPassed,
        "trainTotal": iteration.trainTotal,
        "results": [
            {
                "query": rate.query,
                "shouldTrigger": rate.shouldTrigger,
                "triggerRate": rate.triggerRate,
                "passed": rate.passed,
            }
            for rate in rates
            if rate.query
        ],
    }


def _trigger_decision_triggers(decision: TriggerJudgeDecision, candidate_name: str) -> bool:
    # kept for external/CLI callers and tests
    return _decision_triggers(decision, candidate_name)
import { useState, useCallback } from 'react';
import type { SkillDraft } from '../types';
import { createBlankDraft } from '../data';

export function useDraft() {
  const [draft, setDraft] = useState<SkillDraft>(() => createBlankDraft());

  const updateDraft = useCallback((updates: Partial<SkillDraft>) => {
    setDraft((prev) => ({ ...prev, ...updates, updatedAt: Date.now() }));
  }, []);

  const updateTrigger = useCallback((updates: Partial<SkillDraft['trigger']>) => {
    setDraft((prev) => ({
      ...prev,
      trigger: { ...prev.trigger, ...updates },
      updatedAt: Date.now(),
    }));
  }, []);

  const updateWorkflow = useCallback((updates: Partial<SkillDraft['workflow']>) => {
    setDraft((prev) => ({
      ...prev,
      workflow: { ...prev.workflow, ...updates },
      updatedAt: Date.now(),
    }));
  }, []);

  const updateContext = useCallback((updates: Partial<SkillDraft['context']>) => {
    setDraft((prev) => ({
      ...prev,
      context: { ...prev.context, ...updates },
      updatedAt: Date.now(),
    }));
  }, []);

  const updateKnowledge = useCallback((updates: Partial<SkillDraft['knowledge']>) => {
    setDraft((prev) => ({
      ...prev,
      knowledge: { ...prev.knowledge, ...updates },
      updatedAt: Date.now(),
    }));
  }, []);

  const updateOutputControl = useCallback((updates: Partial<SkillDraft['outputControl']>) => {
    setDraft((prev) => ({
      ...prev,
      outputControl: { ...prev.outputControl, ...updates },
      updatedAt: Date.now(),
    }));
  }, []);

  const resetDraft = useCallback(() => {
    setDraft(createBlankDraft());
  }, []);

  return {
    draft,
    setDraft,
    updateDraft,
    updateTrigger,
    updateWorkflow,
    updateContext,
    updateKnowledge,
    updateOutputControl,
    resetDraft,
  };
}

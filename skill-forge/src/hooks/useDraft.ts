import { useState, useCallback } from 'react';
import type { SkillDraft } from '../types';
import { createBlankDraft } from '../data';

export function useDraft() {
  const [draft, setDraft] = useState<SkillDraft>(() => createBlankDraft());

  const updateDraft = useCallback((updates: Partial<SkillDraft>) => {
    setDraft((prev) => ({ ...prev, ...updates, updatedAt: Date.now() }));
  }, []);

  const updatePurpose = useCallback((updates: Partial<SkillDraft['purpose']>) => {
    setDraft((prev) => ({
      ...prev,
      purpose: { ...prev.purpose, ...updates },
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

  const resetDraft = useCallback(() => {
    setDraft(createBlankDraft());
  }, []);

  return {
    draft,
    setDraft,
    updateDraft,
    updatePurpose,
    updateKnowledge,
    resetDraft,
  };
}

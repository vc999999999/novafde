import {
  createDraft,
  generateDraft,
  listCliCommands,
  listHistory,
  listModelProviders,
  listRules,
  toGenerationDownloadUrl,
} from './api';
import type {
  CliCommandHelp,
  GenerationResult,
  HistoryItem,
  ModelProviderConfig,
  QualityRule,
  SkillDraft,
} from './types';

export async function apiContractCheck(draft: SkillDraft) {
  const savedDraft: SkillDraft = await createDraft(draft);
  const generation: GenerationResult = await generateDraft(savedDraft.id);
  const history: HistoryItem[] = await listHistory();
  const rules: QualityRule[] = await listRules();
  const providers: ModelProviderConfig[] = await listModelProviders();
  const commands: CliCommandHelp[] = await listCliCommands();
  const downloadUrl: string = toGenerationDownloadUrl(generation.id);

  return {
    savedDraft,
    generation,
    history,
    rules,
    providers,
    commands,
    downloadUrl,
  };
}

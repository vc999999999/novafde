import { render, screen } from '@testing-library/react';
import SkillSpecPanel from './SkillSpecPanel';
import type { SkillSpecResponse } from '../types';


const response: SkillSpecResponse = {
  current: {
    schemaVersion: '1.0',
    revision: 2,
    identity: {
      skillName: 'product-research',
      displayName: 'Product Research',
      targetPlatforms: ['codex'],
      outputLanguage: 'zh-CN',
    },
    activationContract: {
      usage: '当产品团队需要竞品调研时使用',
      desiredOutcome: '形成可验证的研究结论',
    },
    workflowStages: [
      {
        id: 'workflow.stage.01',
        statement: '整理证据',
        source: 'user',
        required: true,
      },
    ],
    completionCriteria: '每个结论都有来源',
    specialCases: '',
    incrementalKnowledge: ['区分事实、推断和假设'],
    pitfalls: [],
    hardRestrictions: ['不得编造来源'],
    restrictionItems: [],
    fileContract: {
      needsReferences: true,
      needsScripts: false,
      needsAssets: false,
    },
    relatedSkills: [],
    acceptanceCriteria: [
      {
        id: 'acceptance.01',
        statement: '每个结论都有来源',
        source: 'user',
        required: true,
      },
    ],
    userSupplements: [
      {
        id: 'supplement.issue-1',
        question: '什么条件代表流程结束？',
        statement: '[什么条件代表流程结束？] 通过负责人复核。',
        source: 'user',
      },
    ],
    sourceIssueIds: [],
  },
  revision: 2,
  sha256: 'a'.repeat(64),
  revisions: [
    {
      revision: 1,
      sha256: 'b'.repeat(64),
      createdAt: 1,
      sourceIssueIds: [],
    },
    {
      revision: 2,
      sha256: 'a'.repeat(64),
      createdAt: 2,
      sourceIssueIds: [],
    },
  ],
};


test('renders the read-only SDD specification', () => {
  render(<SkillSpecPanel response={response} />);

  expect(screen.getByText('生成规格')).toBeInTheDocument();
  expect(screen.getByText('Revision 2')).toBeInTheDocument();
  expect(screen.getByText('当产品团队需要竞品调研时使用')).toBeInTheDocument();
  expect(screen.getByText('整理证据')).toBeInTheDocument();
  expect(screen.getByText('不得编造来源')).toBeInTheDocument();
  expect(screen.getByText('每个结论都有来源')).toBeInTheDocument();
  expect(screen.getByText('用户补充')).toBeInTheDocument();
  expect(
    screen.getByText('[什么条件代表流程结束？] 通过负责人复核。'),
  ).toBeInTheDocument();
});


test('renders compatibility copy for historical generations without a spec', () => {
  render(<SkillSpecPanel response={null} unavailable />);

  expect(screen.getByText('此历史版本无 SDD 规格')).toBeInTheDocument();
});

test('renders a local error notice when the spec fails to load', () => {
  render(
    <SkillSpecPanel response={null} error="生成规格加载失败，请稍后刷新。" />,
  );

  expect(screen.getByText('生成规格')).toBeInTheDocument();
  expect(screen.getByText('生成规格加载失败，请稍后刷新。')).toBeInTheDocument();
});

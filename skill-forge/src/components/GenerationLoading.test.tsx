import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import GenerationLoading from './GenerationLoading';


test('renders the active quality stage and repair round', () => {
  render(
    <GenerationLoading
      stage="evaluating-implementation"
      progress={64}
      currentRound={2}
      maxRepairRounds={3}
    />,
  );

  expect(screen.getByText('正在评估工作流实现质量')).toBeInTheDocument();
  expect(screen.getByText('第 2/3 轮优化')).toBeInTheDocument();
});

test('renders staged attempt details and lets the user stop generation', async () => {
  const user = userEvent.setup();
  const onCancel = vi.fn();

  render(
    <GenerationLoading
      stage="generating-workflow"
      progress={18}
      currentRound={0}
      maxRepairRounds={3}
      stageAttempt={2}
      stageMaxAttempts={3}
      completedStages={[]}
      stageMessage="工作流骨架未通过检查，正在重试"
      onCancel={onCancel}
    />,
  );

  expect(screen.getByText('正在构建工作流骨架')).toBeInTheDocument();
  expect(screen.getByText('第 2/3 次尝试')).toBeInTheDocument();
  expect(screen.getByText('质量优先，不限制单次任务总预算与总时长')).toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: '停止生成' }));
  expect(onCancel).toHaveBeenCalledOnce();
});

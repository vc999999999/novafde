import { render, screen } from '@testing-library/react';
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

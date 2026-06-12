import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createBlankDraft } from '../../data';
import PurposeStep from './PurposeStep';


test('keeps only the essential purpose inputs expanded by default', async () => {
  const user = userEvent.setup();
  const draft = createBlankDraft();
  const onUpdatePurpose = vi.fn();
  const { container } = render(
    <PurposeStep draft={draft} onUpdatePurpose={onUpdatePurpose} />,
  );

  expect(screen.getByText('什么时候使用')).toBeInTheDocument();
  expect(screen.getByText('希望得到什么结果')).toBeInTheDocument();
  expect(screen.getByText('可选质量增强')).toBeInTheDocument();

  const details = container.querySelector('details');
  expect(details).not.toHaveAttribute('open');

  await user.click(screen.getByText('可选质量增强'));

  expect(details).toHaveAttribute('open');
  expect(screen.getByText('大致执行流程（可选）')).toBeInTheDocument();
  expect(screen.getByText('完成标准（可选）')).toBeInTheDocument();
  expect(screen.getByText('特殊情况（可选）')).toBeInTheDocument();
});

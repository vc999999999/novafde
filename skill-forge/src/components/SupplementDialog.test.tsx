import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SupplementDialog from './SupplementDialog';


test('collects targeted answers and submits them by issue id', async () => {
  const user = userEvent.setup();
  let submitted: Array<{ issueId: string; answer: string | string[] }> = [];
  render(
    <SupplementDialog
      questions={[
        {
          issueId: 'completion-fact',
          question: '什么条件代表流程完成？',
          inputControl: 'long-text',
          options: [],
          existingAnswer: null,
        },
      ]}
      scores={{ overall: 78, activation: 82, implementation: 74 }}
      submitting={false}
      onSubmit={(answers) => {
        submitted = answers;
      }}
      onSkip={() => undefined}
    />,
  );

  await user.type(screen.getByLabelText('什么条件代表流程完成？'), '负责人复核通过');
  await user.click(screen.getByRole('button', { name: '补充并继续' }));

  expect(submitted).toEqual([
    { issueId: 'completion-fact', answer: '负责人复核通过' },
  ]);
});

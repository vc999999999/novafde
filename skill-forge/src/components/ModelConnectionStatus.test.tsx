import { render, screen } from '@testing-library/react';
import ModelConnectionStatus from './ModelConnectionStatus';


test('shows the connected model in the single global status control', () => {
  render(
    <ModelConnectionStatus
      connection={{
        status: 'connected',
        generationProvider: {
          id: 'provider_1',
          name: 'Claude',
          model: 'claude-sonnet',
          protocol: 'anthropic',
        },
        judgeProvider: null,
        checkedAt: '2026-06-10T00:00:00Z',
        message: '模型连接可用。',
      }}
      onOpenSettings={() => undefined}
    />,
  );

  expect(screen.getByRole('button', { name: /模型已连接/ })).toHaveTextContent('claude-sonnet');
});

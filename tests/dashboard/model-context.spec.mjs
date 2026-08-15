import { expect, test } from '@playwright/test';

async function checkboxStates(locator) {
  return locator.evaluateAll((inputs) => inputs.map((input, index) => {
    const label = input.closest('label');
    return {
      checked: input.checked,
      index,
      label: label && label.textContent ? label.textContent.replace(/\s+/g, ' ').trim() : '',
      track: input.dataset.track || '',
    };
  }));
}

test('editorial research starts with local models and adds a selected remote model to hard values', async ({ page }) => {
  await page.goto('/index.html');

  const modelContext = page.locator('.model-context');
  await expect(modelContext.getByRole('heading', { name: 'Models', exact: true })).toBeVisible();
  await expect(modelContext).toContainText('Start by choosing the models');

  const [modelTop, costTop] = await Promise.all([
    modelContext.evaluate((element) => element.getBoundingClientRect().top),
    page.getByRole('heading', { name: 'Cost versus quality', exact: true }).evaluate((element) => element.getBoundingClientRect().top),
  ]);
  expect(modelTop).toBeLessThan(costTop);

  const controls = page.locator('#controls input[type="checkbox"]');
  const states = await checkboxStates(controls);
  const localModels = states.filter((state) => state.label.includes('(Local)'));
  const remoteModel = states.find((state) => !state.label.includes('(Local)'));
  expect(localModels.length).toBeGreaterThan(0);
  expect(localModels.every((state) => state.checked)).toBeTruthy();
  expect(remoteModel).toBeDefined();
  expect(remoteModel.checked).toBeFalsy();

  const rowsBefore = await page.locator('#quality-values tbody tr').count();
  await controls.nth(remoteModel.index).check();
  await expect(page.locator('#quality-values tbody tr')).toHaveCount(rowsBefore + 1);
  await expect(page.locator('body')).not.toContainText('SteadyBurn');
});

test('assistant research starts with local models and expands row charts for every selected model', async ({ page }) => {
  await page.goto('/assistant-benchmark.html');

  const modelContext = page.locator('.model-selector');
  await expect(modelContext.getByRole('heading', { name: 'Models', exact: true })).toBeVisible();
  await expect(modelContext).toContainText('Start by choosing the models');

  const [modelTop, chartTop] = await Promise.all([
    modelContext.evaluate((element) => element.getBoundingClientRect().top),
    page.locator('.chart').first().evaluate((element) => element.getBoundingClientRect().top),
  ]);
  expect(modelTop).toBeLessThan(chartTop);

  const controls = page.locator('[data-model-control]');
  const states = await checkboxStates(controls);
  const localModels = states.filter((state) => state.track === 'local');
  const remoteModels = states.filter((state) => state.track === 'openrouter');
  expect(localModels.length).toBeGreaterThan(0);
  expect(remoteModels.length).toBeGreaterThan(0);
  expect(localModels.every((state) => state.checked)).toBeTruthy();
  expect(remoteModels.every((state) => !state.checked)).toBeTruthy();

  const scoreChart = page.locator('#assistant-score');
  const initialHeight = Number(await scoreChart.getAttribute('height'));
  await page.getByRole('button', { name: 'Select all', exact: true }).click();
  await expect.poll(async () => Number(await scoreChart.getAttribute('height'))).toBeGreaterThan(initialHeight);
  await expect(controls).toHaveCount(states.length);
  await expect(page.locator('body')).not.toContainText('SteadyBurn');
});

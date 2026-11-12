const { defineConfig } = require('@playwright/test');
// Opt in explicitly for a CPU-emulated VM; normal acceptance keeps strict defaults.
const emulated = process.env.E2E_EMULATED === '1';
module.exports = defineConfig({
  testDir: '.', timeout: emulated ? 600000 : 180000, workers: 1, retries: 0,
  expect: { timeout: emulated ? 30000 : 5000 },
  reporter: [['list'], ['json', { outputFile: 'test-results/report.json' }]],
  use: { baseURL: process.env.E2E_BASE_URL || 'http://web', trace: 'retain-on-failure' },
  projects: process.env.E2E_CHROME === '1' ? [{ name: 'chrome', use: { browserName: 'chromium', channel: 'chrome' } }] : ['chromium', 'firefox', 'webkit'].map(browserName => ({ name: browserName, use: { browserName, ...(browserName === "chromium" ? { channel: "chromium" } : {}) } })),
});

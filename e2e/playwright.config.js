const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: '.', timeout: 180000, workers: 1, retries: 0,
  reporter: [['list']],
  use: { baseURL: process.env.E2E_BASE_URL || 'http://web', trace: 'retain-on-failure' },
  projects: process.env.E2E_CHROME === '1' ? [{ name: 'chrome', use: { browserName: 'chromium', channel: 'chrome' } }] : ['chromium', 'firefox', 'webkit'].map(browserName => ({ name: browserName, use: { browserName, ...(browserName === "chromium" ? { channel: "chromium" } : {}) } })),
});

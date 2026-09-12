import { expect, test } from "@playwright/test";

// case-research-dashboard had no e2e coverage at all before this: main carried
// no .federation/gui-capabilities.json and no scripts/check_gui_parity.py — the
// gate itself was missing, not just failing. This spec runs against the real
// backend and the real committed ledgers (470 master cases, a live candidate
// queue) rather than stubs, and cross-checks what's rendered against what the
// API actually returned, so a mutation that breaks the data path fails a named
// test instead of silently shipping.

test("Cases tab renders the real case count and the search box filters it", async ({ page }) => {
  const casesResponse = page.waitForResponse(
    (response) => response.url().includes("/cases") && response.status() === 200,
  );
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const cases = await (await casesResponse).json();
  expect(Array.isArray(cases), "GET /cases did not return an array").toBe(true);
  expect(cases.length, "the committed master ledger should not be empty").toBeGreaterThan(0);

  const countBadge = page.locator("input[placeholder='Search…']").locator("xpath=preceding-sibling::span[1]");
  await expect(countBadge).toHaveText(String(cases.length));

  // A query that cannot match any real description or location string.
  await page.getByPlaceholder("Search…").fill("zzz-no-such-sighting-zzz");
  await expect(countBadge).toHaveText("0");
});

test("the evidence-tier filter narrows the grid to matching real cases", async ({ page }) => {
  const casesResponse = page.waitForResponse(
    (response) => response.url().includes("/cases") && response.status() === 200,
  );
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const cases = await (await casesResponse).json();
  const t1Count = cases.filter((c) => c.evidence_tier === "T1").length;

  // Two comboboxes render in the filter row: decade first, evidence tier second.
  await page.getByRole("combobox").nth(1).click();
  await page.getByRole("option", { name: "T1" }).click();

  const countBadge = page.locator("input[placeholder='Search…']").locator("xpath=preceding-sibling::span[1]");
  await expect(countBadge).toHaveText(String(t1Count));
});

test("Statistics tab renders the real totals from the backend", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const statsResponse = page.waitForResponse(
    (response) => response.url().includes("/stats") && response.status() === 200,
  );
  await page.getByRole("tab", { name: "Statistics" }).click();
  const stats = await (await statsResponse).json();

  await expect(page.getByText("Total")).toBeVisible();
  await expect(page.getByText(String(stats.total), { exact: true })).toBeVisible();
  await expect(page.getByText(String(stats.mapped), { exact: true })).toBeVisible();
});

test("Candidates tab renders the real review queue", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const candidatesResponse = page.waitForResponse(
    (response) => response.url().includes("/candidates") && response.status() === 200,
  );
  await page.getByRole("tab", { name: "Candidates" }).click();
  const candidates = await (await candidatesResponse).json();

  await expect(page.getByText(`${candidates.length} candidates in queue`)).toBeVisible();
  if (candidates.length > 0) {
    await expect(page.getByText(candidates[0].candidate_id, { exact: true })).toBeVisible();
  }
});

test("map density failure can retry into evidence and spatial tools are discoverable", async ({ page }) => {
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  let attempts = 0;
  await page.route("**/municipios/case_density", async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify({ detail: "test outage" }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify({
        by_geoid: { "72127": 1 },
        matched_count: 1,
        matched_by_method: { point_in_polygon: 1 },
        unmatched: 1,
        unresolved_by_reason: { NO_COORDINATES: 1 },
        total_cases: 2,
        scope: { identity_effect: "NONE", state: "CANDIDATE_NOT_IDENTITY" },
      }),
    });
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /^Density/ }).click();
  await expect(page.getByText("Density unavailable; no zero-case inference was made.")).toBeVisible();
  expect(consoleErrors).toEqual([
    "Failed to load resource: the server responded with a status of 503 (Service Unavailable)",
  ]);
  consoleErrors.length = 0;
  await page.getByRole("button", { name: "Retry density" }).click();
  await expect(page.getByText(/1 matched · 1 unresolved · 2 total/)).toBeVisible();

  await page.getByRole("button", { name: "Spatial tools" }).click();
  await page.getByRole("button", { name: "Buffer" }).click();
  await expect(page.getByLabel("Spatial tool target")).toBeVisible();
  await page.getByRole("button", { name: "10 km" }).click();
  await expect(page.getByRole("button", { name: "10 km" })).toHaveAttribute("aria-pressed", "true");
  expect(consoleErrors).toEqual([]);
});

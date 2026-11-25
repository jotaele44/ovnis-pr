import { expect, test } from "@playwright/test";

// The mobile shell (<= 860px): header + bottom navigation + card list + bottom
// sheet, per the federation GUI spec. Like gui-parity.spec.mjs this runs against
// the real backend and the real ledgers. Reference viewports: iPhone 390x844,
// iPhone wide 430x932, and phone landscape 844x390.
//
// Emulated viewports are not a physical iPhone/Capacitor run: safe-area insets
// are 0 here and the keyboard/system bars are not exercised. That check stays
// OPEN until it is done on a device.

const hasNoHorizontalOverflow = (page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

async function openCases(page) {
  const casesResponse = page.waitForResponse(
    (response) => response.url().includes("/cases") && response.status() === 200,
  );
  await page.goto("/", { waitUntil: "domcontentloaded" });
  return (await casesResponse).json();
}

test.describe("iPhone portrait 390x844", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("shows the mobile shell: bottom nav of five, no desktop side pane", async ({ page }) => {
    await openCases(page);
    const nav = page.getByRole("navigation", { name: "OVNIS mobile navigation" });
    await expect(nav.getByRole("button")).toHaveCount(5);
    for (const name of ["Cases", "Map", "Statistics", "Candidates", "More"]) {
      await expect(nav.getByRole("button", { name })).toBeVisible();
    }
    await expect(page.getByRole("tablist")).toHaveCount(0);
    expect(await hasNoHorizontalOverflow(page)).toBe(true);
  });

  test("touch targets are at least 44px and the header is at least 54px", async ({ page }) => {
    await openCases(page);
    const small = await page.evaluate(() => {
      const interactive = [
        ...document.querySelectorAll("header button, nav button, main button, main input, main [role='combobox']"),
      ];
      return interactive
        .map((el) => ({ label: el.getAttribute("aria-label") || el.textContent?.trim() || el.tagName, box: el.getBoundingClientRect() }))
        .filter(({ box }) => box.height < 44 || box.width < 44)
        .map(({ label, box }) => `${label}: ${Math.round(box.width)}x${Math.round(box.height)}`);
    });
    expect(small).toEqual([]);
    const header = await page.locator("header").boundingBox();
    expect(header.height).toBeGreaterThanOrEqual(54);
  });

  test("a filter chip and the sheet close button are touch-sized too", async ({ page }) => {
    const cases = await openCases(page);
    await page.getByRole("searchbox", { name: "Search cases" }).fill(cases[0].case_id);
    const chip = await page.getByRole("button", { name: /Remove filter/ }).boundingBox();
    expect(chip.height).toBeGreaterThanOrEqual(44);
    await page.getByRole("list", { name: "Cases" }).getByRole("button").first().click();
    const close = await page.getByRole("dialog").getByRole("button", { name: "Close" }).boundingBox();
    expect(close.width).toBeGreaterThanOrEqual(44);
    expect(close.height).toBeGreaterThanOrEqual(44);
  });

  test("lists the real cases as cards, 12 to a page, with a working empty state", async ({ page }) => {
    const cases = await openCases(page);
    await expect(page.getByRole("table")).toHaveCount(0);
    await expect(page.getByTestId("case-count")).toHaveText(String(cases.length));
    await expect(page.getByRole("list", { name: "Cases" }).getByRole("listitem")).toHaveCount(Math.min(12, cases.length));

    await page.getByRole("searchbox", { name: "Search cases" }).fill("zzz-no-such-sighting-zzz");
    await expect(page.getByText("No cases found")).toBeVisible();
    await page.getByRole("button", { name: "Reset search" }).click();
    await expect(page.getByTestId("case-count")).toHaveText(String(cases.length));
  });

  test("tapping a case opens its record in a bottom sheet", async ({ page }) => {
    const cases = await openCases(page);
    await page.getByRole("list", { name: "Cases" }).getByRole("button").first().click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible();
    await expect(sheet).toContainText(cases[0].case_id);
    const viewport = page.viewportSize();
    // The sheet slides in; measure once it has settled against the bottom edge.
    await expect
      .poll(async () => {
        const box = await sheet.boundingBox();
        return Math.round(box.y + box.height);
      })
      .toBe(viewport.height);
    const box = await sheet.boundingBox();
    // Leaves the list visible above it, and spans the full width.
    expect(box.height).toBeLessThanOrEqual(viewport.height * 0.86);
    expect(box.width).toBeGreaterThanOrEqual(viewport.width - 1);
  });

  test("Statistics and Candidates are reachable from the bottom nav with real data", async ({ page }) => {
    await openCases(page);
    const statsResponse = page.waitForResponse(
      (response) => response.url().includes("/stats") && response.status() === 200,
    );
    await page.getByRole("button", { name: "Statistics" }).click();
    const stats = await (await statsResponse).json();
    // The case list stays mounted (hidden) behind this view, so match only what is shown.
    await expect(page.getByText(String(stats.total), { exact: true }).filter({ visible: true })).toBeVisible();

    const candidatesResponse = page.waitForResponse(
      (response) => response.url().includes("/candidates") && response.status() === 200,
    );
    await page.getByRole("button", { name: "Candidates" }).click();
    const candidates = await (await candidatesResponse).json();
    await expect(page.getByText(`${candidates.length} candidates in queue`)).toBeVisible();
    expect(await hasNoHorizontalOverflow(page)).toBe(true);
  });

  test("Activity lives in the More sheet", async ({ page }) => {
    await openCases(page);
    await page.getByRole("button", { name: "More" }).click();
    await page.getByRole("button", { name: "Activity" }).click();
    await expect(page.getByRole("region", { name: "Program timeline and upcoming work" })).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("the map view keeps its layer controls clear of the zoom control", async ({ page }) => {
    await openCases(page);
    await page.getByRole("button", { name: "Map" }).click();
    const spatial = await page.getByRole("button", { name: "Spatial tools" }).boundingBox();
    const zoomIn = await page.getByRole("button", { name: "Zoom in" }).boundingBox();
    const overlaps =
      spatial.x < zoomIn.x + zoomIn.width && spatial.x + spatial.width > zoomIn.x &&
      spatial.y < zoomIn.y + zoomIn.height && spatial.y + spatial.height > zoomIn.y;
    expect(overlaps).toBe(false);
    expect(await hasNoHorizontalOverflow(page)).toBe(true);
  });

  test("language and theme switch from the header and persist across a reload", async ({ page }) => {
    await openCases(page);
    await page.getByRole("button", { name: "Español" }).click();
    await expect(page.getByRole("navigation").getByRole("button", { name: "Casos" })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("lang", "es");

    await page.getByRole("button", { name: /^Tema: oscuro/ }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByRole("navigation").getByRole("button", { name: "Casos" })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });
});

test.describe("iPhone wide portrait 430x932", () => {
  test.use({ viewport: { width: 430, height: 932 }, hasTouch: true, isMobile: true });

  test("fits without horizontal overflow on every view", async ({ page }) => {
    await openCases(page);
    for (const name of ["Cases", "Map", "Statistics", "Candidates"]) {
      await page.getByRole("button", { name, exact: true }).click();
      expect(await hasNoHorizontalOverflow(page), name).toBe(true);
    }
  });
});

test.describe("phone landscape 844x390", () => {
  test.use({ viewport: { width: 844, height: 390 }, hasTouch: true, isMobile: true });

  test("still uses the mobile shell, fits, and keeps the nav reachable", async ({ page }) => {
    await openCases(page);
    await expect(page.getByRole("navigation", { name: "OVNIS mobile navigation" })).toBeVisible();
    expect(await hasNoHorizontalOverflow(page)).toBe(true);
    // Filters share one row so a card is visible above the pager.
    const search = await page.getByRole("searchbox", { name: "Search cases" }).boundingBox();
    const period = await page.getByRole("combobox", { name: "Period" }).boundingBox();
    expect(Math.abs(search.y - period.y)).toBeLessThan(30);
  });
});

test.describe("desktop 1440x900 keeps the side-pane layout", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("no bottom navigation; the tabbed side pane is present", async ({ page }) => {
    await openCases(page);
    await expect(page.getByRole("navigation", { name: "OVNIS mobile navigation" })).toHaveCount(0);
    await expect(page.getByRole("tablist")).toBeVisible();
  });
});

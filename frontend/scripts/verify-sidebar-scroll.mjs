/**
 * Verifica scroll del sidebar en tablet/escritorio y ausencia de regresión en móvil.
 *
 * Uso:
 *   npm run build && npm run preview -- --host 127.0.0.1 --port 4173
 *   node scripts/verify-sidebar-scroll.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE_URL = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const OUT_DIR = path.resolve(__dirname, "../../docs/screenshots/sidebar-scroll");

const DESKTOP_VIEWPORTS = [
  { w: 768, h: 1024, tag: "768x1024" },
  { w: 1024, h: 768, tag: "1024x768" },
  { w: 1024, h: 600, tag: "1024x600" },
  { w: 1280, h: 600, tag: "1280x600" },
  { w: 1366, h: 768, tag: "1366x768" },
];

const MOBILE_VIEWPORT = { w: 390, h: 844, tag: "390x844" };

async function waitForUrl(url, timeoutMs = 60000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error(`Preview no disponible: ${url}`);
}

async function login(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="text"], input[name="usuario_login"], #usuario', "admin").catch(() => {});
  const userInput = page.locator('input[placeholder*="usuario" i], input[type="text"]').first();
  const passInput = page.locator('input[type="password"]').first();
  await userInput.fill("admin");
  await passInput.fill("admin123");
  await page.locator('button[type="submit"], .btn--primary').first().click();
  await page.waitForSelector(".app-shell", { timeout: 20000 });
}

async function assertDesktopNavScroll(page, tag) {
  const result = await page.evaluate(() => {
    const nav = document.querySelector(".sidebar__nav");
    const sidebar = document.querySelector(".sidebar");
    if (!nav || !sidebar) return { ok: false, reason: "sidebar/nav missing" };
    const csNav = getComputedStyle(nav);
    const csSidebar = getComputedStyle(sidebar);
    const scrollable = nav.scrollHeight > nav.clientHeight;
    nav.scrollTop = nav.scrollHeight;
    const scrolled = nav.scrollTop > 0;
    const links = nav.querySelectorAll(".sidebar__link");
    const lastLink = links[links.length - 1];
    const lastVisible =
      lastLink &&
      lastLink.getBoundingClientRect().top >= nav.getBoundingClientRect().top &&
      lastLink.getBoundingClientRect().bottom <= nav.getBoundingClientRect().bottom + 2;
    return {
      ok:
        csNav.overflowY === "auto" &&
        csSidebar.overflowY === "hidden" &&
        scrollable &&
        scrolled,
      overflowY: csNav.overflowY,
      sidebarOverflowY: csSidebar.overflowY,
      scrollHeight: nav.scrollHeight,
      clientHeight: nav.clientHeight,
      scrollTop: nav.scrollTop,
      lastLinkText: lastLink?.textContent?.trim() ?? null,
      lastVisibleAfterScroll: Boolean(lastVisible),
    };
  });
  if (!result.ok) {
    throw new Error(`[${tag}] desktop nav scroll failed: ${JSON.stringify(result)}`);
  }
  return result;
}

async function assertMobileUnchanged(page) {
  const result = await page.evaluate(() => {
    const nav = document.querySelector(".sidebar__nav");
    const sidebar = document.querySelector(".sidebar");
    const csNav = nav ? getComputedStyle(nav) : null;
    const csSidebar = sidebar ? getComputedStyle(sidebar) : null;
    return {
      navOverflowY: csNav?.overflowY ?? null,
      sidebarOverflowY: csSidebar?.overflowY ?? null,
    };
  });
  if (result.sidebarOverflowY !== "auto") {
    throw new Error(`[390x844] mobile sidebar should scroll as whole: ${JSON.stringify(result)}`);
  }
  if (result.navOverflowY === "auto") {
    throw new Error(`[390x844] mobile nav should not have overflow-y auto: ${JSON.stringify(result)}`);
  }
}

async function captureSidebar(page, tag, suffix) {
  const sidebar = page.locator(".sidebar");
  await sidebar.screenshot({
    path: path.join(OUT_DIR, tag, `sidebar-${suffix}.png`),
  });
}

async function main() {
  await waitForUrl(BASE_URL);
  await mkdir(OUT_DIR, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  await login(page);

  for (const vp of DESKTOP_VIEWPORTS) {
    await mkdir(path.join(OUT_DIR, vp.tag), { recursive: true });
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "networkidle" });
    await page.waitForSelector(".sidebar__nav");
    await captureSidebar(page, vp.tag, "top");
    const info = await assertDesktopNavScroll(page, vp.tag);
    await page.evaluate(() => {
      const nav = document.querySelector(".sidebar__nav");
      nav.scrollTop = nav.scrollHeight;
    });
    await page.waitForTimeout(200);
    await captureSidebar(page, vp.tag, "bottom");
    console.log(`OK ${vp.tag}: scrollTop=${info.scrollTop}, last=${info.lastLinkText}`);
  }

  await page.setViewportSize({ width: MOBILE_VIEWPORT.w, height: MOBILE_VIEWPORT.h });
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "networkidle" });
  await assertMobileUnchanged(page);
  console.log(`OK ${MOBILE_VIEWPORT.tag}: mobile sidebar behavior unchanged`);

  await browser.close();
  console.log(`Capturas en ${OUT_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

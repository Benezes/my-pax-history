import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const BASE = process.env.E2E_BASE_URL || "http://127.0.0.1:5173";
const OUT = process.env.E2E_OUT || "/opt/cursor/artifacts";
const ACTION =
  "Proponho uma reforma tributária ampla, simplificando impostos sobre consumo e tocando a unificação de PIS, Cofins e ICMS com transição gradual e compensação aos estados.";

const VIEWPORTS = [
  { name: "390x844", width: 390, height: 844 },
  { name: "1024x600", width: 1024, height: 600 },
  { name: "1280x800", width: 1280, height: 800 },
  { name: "1920x1080", width: 1920, height: 1080 },
];

async function waitForServer() {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(BASE);
      if (res.ok) return;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Frontend not reachable at ${BASE}`);
}

async function startGame(page) {
  await page.goto(`${BASE}/?globe=fallback`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Nova partida" }).click();
  await page.getByRole("button", { name: /Simulação offline/ }).click();
  await page.getByRole("button", { name: "Assumir a Presidência" }).click();
  await page.getByPlaceholder(/Ex\.: Propor/).waitFor({ timeout: 30_000 });
}

async function shot(page, name) {
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

async function runViewport(browser, vp) {
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
  await startGame(page);
  const box = page.getByPlaceholder(/Ex\.: Propor/);
  await box.fill(ACTION);
  await page.getByRole("button", { name: "E se?" }).click();
  await page.locator('[data-ai-job="whatif"]').waitFor({ timeout: 10_000 });
  await page.waitForTimeout(1200);
  await shot(page, `loading-whatif-${vp.name}`);
  await page.locator(".whatif").waitFor({ timeout: 120_000 });

  await page.getByRole("button", { name: "Registrar ação" }).click();
  await page.getByRole("button", { name: "Ver texto completo" }).click();
  await shot(page, `queued-expanded-${vp.name}`);

  await page.getByRole("button", { name: "Avançar 1 mês" }).click();
  await page.locator('[data-ai-job="advance"]').waitFor({ timeout: 10_000 });
  await page.waitForTimeout(1200);
  await shot(page, `loading-advance-${vp.name}`);
  await page.locator('[data-ai-job="advance"]').waitFor({ state: "detached", timeout: 120_000 });

  const dossie = page.getByRole("button", { name: "Dossiê" });
  if (await dossie.isVisible()) await dossie.click();
  await page.getByRole("button", { name: "Assessor" }).click();
  await page.getByPlaceholder("Pergunte ao assessor...").fill("Como está a inflação?");
  await page.getByRole("button", { name: "Enviar" }).click();
  await page.locator('[data-ai-job="advisor"]').waitFor({ timeout: 10_000 });
  await page.waitForTimeout(1200);
  await shot(page, `loading-advisor-${vp.name}`);
  await page.locator('[data-ai-job="advisor"]').waitFor({ state: "detached", timeout: 120_000 });
  await page.close();
}

await mkdir(OUT, { recursive: true });
await waitForServer();
const browser = await chromium.launch({ args: ["--no-sandbox"] });
try {
  for (const vp of VIEWPORTS) {
    console.log("viewport", vp.name);
    await runViewport(browser, vp);
  }
} finally {
  await browser.close();
}
console.log("screenshots in", OUT);

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const AUTH_FILE = path.join(ROOT, "auth.json");
const TOKEN_URL =
  "https://www.investopedia.com/auth/realms/investopedia/protocol/openid-connect/token";
const LOGIN_URL = "https://www.investopedia.com/simulator";

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function main() {
  const username = process.env.INVESTOPEDIA_USERNAME;
  const password = process.env.INVESTOPEDIA_PASSWORD;

  if (!username || !password) {
    console.error(
      "Missing login environment variables. Start login through session_singleton.py."
    );
    process.exitCode = 2;
    return;
  }

  let browser;
  let tokenResponse = null;

  try {
    browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewport({ width: 1366, height: 768 });
    await page.setDefaultTimeout(10000);

    page.on("response", async (response) => {
      if (response.url() !== TOKEN_URL || !response.ok()) return;
      try {
        const body = await response.json();
        if (body?.access_token && body?.refresh_token) {
          tokenResponse = body;
        }
      } catch {
        // Ignore unrelated or non-JSON responses from the token endpoint.
      }
    });

    await page.goto(LOGIN_URL, { waitUntil: "domcontentloaded", timeout: 30000 });

    const loginButton = await page.waitForSelector(
      '::-p-xpath(//span[contains(text(),"LOG IN")])',
      { timeout: 10000 }
    );
    if (loginButton) await loginButton.click();

    const usernameField = await page.waitForSelector(
      '::-p-xpath(//input[@id="username"])'
    );
    const passwordField = await page.waitForSelector(
      '::-p-xpath(//input[@id="password"])'
    );

    await usernameField.click({ clickCount: 3 });
    await usernameField.type(username);
    await passwordField.click({ clickCount: 3 });
    await passwordField.type(password);

    const signInButton = await page.waitForSelector(
      '::-p-xpath(//input[@id="login"])'
    );
    await signInButton.click();

    // Some login flows show a second password step; only fill it if it appears.
    try {
      const secondPassword = await page.waitForSelector(
        '::-p-xpath(//input[@id="password"])',
        { timeout: 5000 }
      );
      if (secondPassword) {
        const value = await secondPassword.evaluate((el) => el.value || "");
        if (!value) {
          await secondPassword.type(password);
          const secondSubmit = await page.waitForSelector(
            '::-p-xpath(//input[@id="login"])',
            { timeout: 5000 }
          );
          await secondSubmit.click();
        }
      }
    } catch {
      // No second password step is a valid flow.
    }

    const deadline = Date.now() + 30000;
    while (!tokenResponse && Date.now() < deadline) {
      await wait(250);
    }

    if (!tokenResponse) {
      throw new Error("Login completed without receiving a valid token response.");
    }

    fs.writeFileSync(AUTH_FILE, JSON.stringify(tokenResponse), {
      encoding: "utf8",
      mode: 0o600,
    });
    console.log("Investopedia authentication completed.");
  } catch (error) {
    // Deliberately avoid logging the page, form values, or token payload.
    console.error(
      "Investopedia login failed. The website may have changed its login flow; "
      + "check the page selectors and browser setup."
    );
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
  }
}

main();

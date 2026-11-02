import { chromium } from "@playwright/test";
const b = await chromium.launch();
for (const h of [900, 768, 700]) {
  const p = await (await b.newContext({ viewport: { width: 1440, height: h }, reducedMotion: "reduce" })).newPage();
  await p.goto("http://localhost:7860/");
  await p.locator(".starter").first().waitFor({ timeout: 30000 });
  console.log(h, JSON.stringify(await p.evaluate(() => {
    const log = document.querySelector(".chat-log"), w = document.querySelector(".welcome"), c = document.querySelector(".composer");
    const lr = log.getBoundingClientRect(), wr = w.getBoundingClientRect();
    return { logH: Math.round(lr.height), scrollTop: log.scrollTop, scrollH: log.scrollHeight, welcomeTop: Math.round(wr.top - lr.top), welcomeH: Math.round(wr.height), composerH: Math.round(c.getBoundingClientRect().height) };
  })));
}
await b.close();

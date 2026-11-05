// Bots → a bot → Jailbreak templates: the synced catalog, applying one to a bot's SOUL.md and putting the old one back.
const { WEB, calls, check, nativeShell } = require('../lib.cjs')

module.exports = async t => {
  const { browser } = t
  const pg = await browser.newPage({ viewport: { width: 375, height: 812 } })
  await pg.addInitScript(nativeShell)
  await pg.addInitScript(() => {
    try {
      localStorage.setItem('hm.welcomeDone', '1')
      localStorage.setItem('hm.setupFlowDone', '1')
      localStorage.setItem('hm.connectedOnce', '1')
    } catch {}
  })
  await pg.goto(WEB + '/')
  await pg.getByPlaceholder('Message Hermux').waitFor({ timeout: 15000 })

  // ── the Bots page lists the default profile ──
  await pg.getByRole('button', { name: /^Sessions/ }).click()
  await pg.locator('.nav-tile', { hasText: 'Bots' }).click()
  const bot = pg.locator('.card .list-main', { hasText: 'Main profile' })
  await bot.waitFor({ timeout: 5000 })
  check((await bot.innerText()).includes('mock-model'), `bots: the main profile shows its model (${await bot.innerText()})`)
  await bot.click()

  // ── the bot sheet's Jailbreak entry ──
  const sheet = pg.locator('.sheet', { hasText: 'default' })
  await sheet.waitFor({ timeout: 3000 })
  const entry = sheet.locator('.menu-item', { hasText: 'Jailbreak templates' })
  check((await entry.count()) === 1, 'jailbreak: the bot sheet offers the entry')
  await entry.click()

  const jb = pg.locator('.sheet', { hasText: 'Jailbreak' })
  await jb.locator('.sheet-title', { hasText: 'Jailbreak · default' }).waitFor({ timeout: 3000 })
  const items = jb.locator('.menu-list .menu-item')
  await items.first().waitFor({ timeout: 5000 })
  const shown = await items.allInnerTexts()
  check(shown.length === 2 && shown[0].includes('gemma4') && shown[0].includes('ollama:'), `jailbreak: the synced catalog is listed with its model hint (${JSON.stringify(shown)})`)
  check((await jb.locator('button', { hasText: 'Restore' }).count()) === 0, 'jailbreak: no Restore until something was applied')
  check((await jb.locator('button', { hasText: 'Download templates' }).count()) === 1, 'jailbreak: the sheet can download the templates')

  // ── apply one: it writes SOUL.md for this bot, and Restore appears ──
  await jb.locator('.menu-item', { hasText: 'gemma4' }).click()
  const restore = jb.locator('button', { hasText: 'Restore' })
  await restore.waitFor({ timeout: 5000 }).then(() => check(true, 'jailbreak: applying a template offers Restore'), () => check(false, 'jailbreak: applying a template offers Restore'))
  const applied = calls().filter(c => c.path === '/api/plugins/hermes-mobile/jailbreak/apply')
  check(applied.length === 1 && applied[0].body.template === 'gemma4' && applied[0].body.profile === 'default', `jailbreak: the apply carries the template and the bot (${JSON.stringify(applied.map(c => c.body))})`)

  // ── restore puts the previous SOUL.md back ──
  await restore.click()
  await pg.waitForFunction(() => true).catch(() => {})
  for (let i = 0; i < 30 && !calls().some(c => c.path === '/api/plugins/hermes-mobile/jailbreak/restore'); i++) await new Promise(r => setTimeout(r, 100))
  check(calls().some(c => c.path === '/api/plugins/hermes-mobile/jailbreak/restore'), 'jailbreak: Restore calls the plugin')
  await pg.close()
}

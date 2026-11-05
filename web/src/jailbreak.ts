// Jailbreak templates (G0DM0D3-style): the app's picker over the template collection in
// togg53192-cmd/jailbreaks. Applying one writes it to the bot's SOUL.md — Hermes's identity slot #1 — so every
// NEW chat in that bot starts with the chosen prompt (existing chats keep the prompt they already built).
import { api } from './api'

const P = '/api/plugins/hermes-mobile'

export interface JailbreakTemplate {
  name: string
  filename: string
  tag: string
  size: number
}

export interface JailbreakState {
  backup: boolean
  chars: number
  head: string
}

export interface JailbreakList {
  ok: boolean
  error?: string
  templates: JailbreakTemplate[]
  state?: JailbreakState
}

/** The synced template catalog plus this profile's current state. Never throws: a failed sync returns ok:false. */
export const loadTemplates = (profile: string) =>
  api<JailbreakList>('GET', `${P}/jailbreaks`, undefined, { profile: false }).catch(
    (e): JailbreakList => ({ ok: false, error: String(e), templates: [] })
  )

/** Clone or fast-forward the upstream template collection. */
export const syncTemplates = () => api<{ ok: boolean; count?: number; error?: string }>('POST', `${P}/jailbreak/sync`, {}, { profile: false })

/** Write one template into a profile's SOUL.md (its previous file is kept as a backup). */
export const applyTemplate = (profile: string, template: string) =>
  api<{ ok: boolean; template: string; chars: number }>('POST', `${P}/jailbreak/apply`, { template, profile }, { profile: false })

/** Put the profile's pre-jailbreak SOUL.md back. */
export const restoreSoul = (profile: string) => api<{ ok: boolean }>('POST', `${P}/jailbreak/restore`, { profile }, { profile: false })

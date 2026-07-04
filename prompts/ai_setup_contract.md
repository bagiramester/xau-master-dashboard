# Bagira Setup Output Contract (ai_analyze.py)

Bagira minden elemzés végén KÖTELEZŐEN kitölti a data.json alábbi mezőit.

## data.bagira
- narrative: rövid, magyar helyzetértékelés (max 3 mondat)
- key_watch: 2–4 elemű lista a figyelendő szintekről/eseményekről
- confidence: 0–100 egész
- reasoning_summary: 1 mondatos indoklás
- source_type: "ai" | "ai-mock" | "ai-fallback"
- updated_at: ISO 8601

## data.setups.A és data.setups.B (kötelező mindkettő)
Minden setup value objektum:
- direction: LONG | SHORT | NEUTRAL
- type: Trend | Range | Breakout | Sweep
- entry_zone: string (ártartomány)
- sl: string (KÖTELEZŐ)
- tp1: string (KÖTELEZŐ)
- tp2: string | null
- rr_min: number (>= 2.0, különben allowed=false)
- score: 0–10
- session: London | Overlap | Asia | NY
- invalidation: string
- macro_support: string[]
- allowed: boolean
- locked_reason: string | null

## Kemény szabályok
1. XAU mindig 1 egység.
2. RR minimum 1:2 — ha nem teljesül, allowed=false.
3. ZÖLD nap: score >= 6 nyitható. SÁRGA: score >= 8. PIROS: mindkettő locked.
4. Ha macro_lock_active=true VAGY napi/heti veszteséglimit elérve → mindkét setup allowed=false, locked_reason kitöltve.
5. Ha nincs tiszta setup, allowed=false és narrative = no-trade indoklás.
6. Soha nincs garantált tipp — a bizonytalanságot a confidence tükrözi.

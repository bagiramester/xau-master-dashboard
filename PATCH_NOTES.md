# Dashboard Full Upgrade — Patch Notes

## Új fájlok
| Fájl | Leírás |
|---|---|
| `js/workflows.js` | Közös GitHub Workflow helpers: PAT, dispatchWorkflow, pollDataJsonChange |
| `js/tradelog.js` | Trade Log submit handler: buildTradePayload, validateClosedTrade, submitTradeLog |
| `js/panels.js` | Session countdown, makró timeline, FedWatch bar render |
| `scripts/append_trade.py` | Server-side trade append + performance stats update |
| `.github/workflows/log-trade.yml` | GitHub Actions workflow: log-trade dispatch |
| `css/upgrade-components.css` | Új panel CSS osztályok |
| `prompts/ai_setup_contract.md` | Bagira AI output contract |

## Módosítandó fájlok (manuális patch)

### js/macro.js
- `refreshAllData` függvény cseréje: `macro.refreshAllData.patch.js` tartalma alapján.
- Hozzáadandó: `const DATA_WORKFLOW_FILE = 'update-data.yml';`

### js/bagira.js
- Duplikált definíciók törlése: `GITHUB_OWNER`, `GITHUB_REPO`, `PAT_STORAGE_KEY`, `getPat`, `setPat`, `promptForPat`
- `triggerAiRefresh()` átírása a közös helperekre: `bagira.refactor.patch.js` alapján.

### js/app.js
- `render(data)` függvénybe: `renderPanels(data);` hozzáadása (`renderWarnings` után)
- Submit handler: `submit.addEventListener('click', submitTradeLog);` (`app.submit.patch.js`)
- `tradelog.js` betöltése `app.js` ELŐTT az `index.html`-ben.

### scripts/validate_data.py
- `validate_trade_log(data)` függvény hozzáadása: `validate_data.trade_log.patch.py` alapján.
- Hívás: séma-validáció után `validate_trade_log(data)`

### index.html
- Teljes csere szükséges (script load sorrend és új HTML elemek)
- Sorrend: `workflows.js` → `panels.js` → `tradelog.js` → `macro.js` → `bagira.js` → `app.js`
- CSS: `<link rel="stylesheet" href="css/upgrade-components.css">`

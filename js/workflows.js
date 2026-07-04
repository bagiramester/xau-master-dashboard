// ═══ GITHUB WORKFLOW HELPERS — shared PAT + dispatch + data.json polling ═══
const GITHUB_OWNER = window.GITHUB_OWNER || 'bagiramester';
const GITHUB_REPO = window.GITHUB_REPO || 'xau-master-dashboard';
const PAT_STORAGE_KEY = window.PAT_STORAGE_KEY || 'bagira_gh_pat';

const getPat = () => {
  try { return localStorage.getItem(PAT_STORAGE_KEY) || ''; } catch { return ''; }
};
const setPat = (pat) => {
  try { localStorage.setItem(PAT_STORAGE_KEY, pat || ''); return true; } catch { return false; }
};
const promptForPat = () => {
  const current = getPat();
  const pat = prompt(
    current ? 'GitHub PAT frissítése (üres = törlés).\nJelenlegi: ' + current.substring(0, 8) + '...' :
    'GitHub Personal Access Token szükséges.\nFine-grained: repo → Actions read/write + Contents read/write.',
    current
  );
  if (pat === null) return null;
  setPat(pat.trim());
  return pat.trim();
};

const githubApiHeaders = (pat) => ({
  'Accept': 'application/vnd.github+json',
  'Authorization': `Bearer ${pat}`,
  'X-GitHub-Api-Version': '2022-11-28',
  'Content-Type': 'application/json',
});

const dispatchWorkflow = async (workflowFile, inputs = {}) => {
  let pat = getPat();
  if (!pat) { pat = promptForPat(); if (!pat) throw new Error('PAT hiányzik'); }
  const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${workflowFile}/dispatches`;
  const res = await fetch(url, {
    method: 'POST',
    headers: githubApiHeaders(pat),
    body: JSON.stringify({ ref: 'main', inputs }),
  });
  if (res.status === 204) return true;
  if (res.status === 401) { setPat(''); throw new Error('PAT érvénytelen'); }
  if (res.status === 403) throw new Error('PAT jogosultság kevés');
  if (res.status === 404) throw new Error('Workflow vagy repo nem található');
  throw new Error(`Workflow dispatch hiba HTTP ${res.status}: ${(await res.text()).slice(0, 160)}`);
};

const getDataJsonSha = async () => {
  const res = await fetch(`https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/commits?path=data.json&per_page=1`, {
    cache: 'no-store', headers: { 'Accept': 'application/vnd.github+json' }
  });
  if (!res.ok) return '';
  const j = await res.json();
  return j[0]?.sha || '';
};

const fetchDataBySha = async (sha) => {
  const res = await fetch(`https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/${sha}/data.json`, { cache: 'no-store', mode: 'cors' });
  if (!res.ok) throw new Error(`data.json raw HTTP ${res.status}`);
  return res.json();
};

const pollDataJsonChange = async ({ beforeSha, maxAttempts = 18, intervalMs = 10000, onDone, onTimeout }) => {
  let attempt = 0;
  const tick = async () => {
    try {
      const sha = await getDataJsonSha();
      if (sha && sha !== beforeSha) {
        const data = await fetchDataBySha(sha);
        if (onDone) onDone(data, sha);
        return;
      }
    } catch (e) {}
    attempt += 1;
    if (attempt > maxAttempts) { if (onTimeout) onTimeout(); return; }
    setTimeout(tick, intervalMs);
  };
  setTimeout(tick, intervalMs);
};

import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ShieldCheck,
  LayoutDashboard,
  Megaphone,
  ScanLine,
  WandSparkles,
  Scale,
  History,
  Plug,
  Play,
  ArrowUpRight,
  ArrowRight,
  Plus,
  Search,
  ChevronDown,
  Check,
  CheckCircle2,
  Circle,
  Loader2,
  AlertTriangle,
  X,
  Mail,
  Users,
  Globe2,
  LockKeyhole,
  RotateCcw,
  FileCheck2,
  Sparkles,
  Activity,
  PanelLeftClose,
  ExternalLink,
  Send,
  Eye,
  Pencil,
  GitCompareArrows,
  Ban,
  Info,
  CheckCheck,
  Fingerprint,
} from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, Tooltip, Cell } from 'recharts';
import './styles.css';
type Row = Record<string, any>;
const paths = [
  '/',
  '/campaigns',
  '/audit',
  '/remediation',
  '/governance',
  '/history',
  '/integrations',
  '/demo',
];
const labels = [
  'Overview',
  'Campaigns',
  'AI Audit Center',
  'Remediation',
  'Governance',
  'Audit History',
  'Integrations',
  'Live Demo',
];
const icons = [LayoutDashboard, Megaphone, ScanLine, WandSparkles, Scale, History, Plug, Play];
const agentInfo = [
  ['Consent Guardian', 'Audience permissions', Users],
  ['Claim Verifier', 'Evidence & accuracy', ShieldCheck],
  ['Inclusion Auditor', 'Language & access', Globe2],
  ['Remediation Coordinator', 'Safer campaign drafts', WandSparkles],
  ['Governance Gate', 'Human accountability', LockKeyhole],
];
async function api(path: string, method = 'GET', body?: unknown) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);
  try {
    const r = await fetch('/api' + path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctrl.signal,
    });
    const data = await r.json();
    if (!r.ok)
      throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
    return data;
  } finally {
    clearTimeout(timer);
  }
}
const human = (s: string = '') => s.replaceAll('_', ' ');
const date = (s: string) =>
  new Date(s).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
function Badge({ value }: { value: string }) {
  return (
    <span className={'badge ' + value}>
      {value === 'approved_for_activation' ? 'Approved for activation' : human(value)}
    </span>
  );
}
function CopyDiff({
  original,
  proposed,
  side,
}: {
  original: string;
  proposed: string;
  side: 'original' | 'proposed';
}) {
  const left = original.split(/(\s+)/),
    right = proposed.split(/(\s+)/);
  let start = 0,
    end = 0;
  while (start < left.length && start < right.length && left[start] === right[start]) start++;
  while (
    end < left.length - start &&
    end < right.length - start &&
    left[left.length - 1 - end] === right[right.length - 1 - end]
  )
    end++;
  const tokens = side === 'original' ? left : right;
  const middle = tokens.slice(start, tokens.length - end).join('');
  return (
    <pre>
      {tokens.slice(0, start).join('')}
      {side === 'original' ? <del>{middle}</del> : <ins>{middle}</ins>}
      {end ? tokens.slice(-end).join('') : ''}
    </pre>
  );
}
function App() {
  const [route, setRoute] = useState(window.location.pathname);
  const [campaigns, setCampaigns] = useState<Row[]>([]);
  const [selected, setSelected] = useState(1);
  const [dash, setDash] = useState<Row | null>(null);
  const [history, setHistory] = useState<Row>({ audits: [], events: [], approvals: [] });
  const [integration, setIntegration] = useState<Row | null>(null);
  const [contacts, setContacts] = useState<Row[]>([]);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [form, setForm] = useState<Row | null>(null);
  const [review, setReview] = useState<Row | null>(null);
  const [reviewer, setReviewer] = useState('Local demo reviewer');
  const [comments, setComments] = useState('');
  const [languageReviewed, setLanguageReviewed] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [revisions, setRevisions] = useState<Row[] | null>(null);
  const [sfResult, setSfResult] = useState<Row | null>(null);
  const [focusAudit, setFocusAudit] = useState<Row | null>(null);
  const campaign = campaigns.find((c) => c.id === selected) || campaigns[0];
  const audit = campaign?.latest_audit;
  const proposal = audit?.remediation;
  const running = audit && ['waiting', 'running'].includes(audit.status);
  const pending = history.approvals.find(
    (p: Row) => p.campaign_id === campaign?.id && p.decision === 'pending',
  );
  const oldAudits = history.audits
    .filter((a: Row) => a.campaign_id === campaign?.id && a.status === 'completed')
    .sort((a: Row, b: Row) => a.id - b.id);
  const before = oldAudits[0];
  const load = async () => {
    const [cs, d, h, i, ct] = await Promise.all([
      api('/campaigns'),
      api('/dashboard'),
      api('/audit-history'),
      api('/integrations/status'),
      api('/contacts'),
    ]);
    setCampaigns(cs);
    setDash(d);
    setHistory(h);
    setIntegration(i);
    setContacts(ct);
    setError('');
  };
  useEffect(() => {
    load().catch((e) => setError(e.message));
    const pop = () => setRoute(window.location.pathname);
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, []);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => load().catch((e) => setError(e.message)), 600);
    return () => clearInterval(timer);
  }, [running]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 4500);
    return () => clearTimeout(timer);
  }, [toast]);
  function nav(path: string) {
    window.history.pushState({}, '', path);
    setRoute(path);
    setMobile(false);
    setFocusAudit(null);
    window.scrollTo(0, 0);
  }
  async function action(label: string, fn: () => Promise<any>, message = 'Saved successfully') {
    if (busy) return;
    setBusy(label);
    try {
      await fn();
      await load();
      if (message) setToast(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }
  function runAudit() {
    if (campaign)
      action(
        'audit',
        () => api(`/campaigns/${campaign.id}/audits`, 'POST'),
        'Audit requested. Agent states come from backend execution.',
      );
  }
  function generate() {
    action(
      'generate',
      () => api(`/audits/${audit.id}/remediation`, 'POST'),
      'Corrections are ready for review.',
    );
  }
  function chooseCorrection(item: Row) {
    if (busy) return;
    const previous = campaigns;
    const selected = !item.selected;
    setCampaigns((rows) =>
      rows.map((c) =>
        c.id !== campaign.id
          ? c
          : {
              ...c,
              latest_audit: {
                ...c.latest_audit,
                remediation: {
                  ...proposal,
                  corrections: proposal.corrections.map((x: Row) =>
                    x.id === item.id ? { ...x, selected } : x,
                  ),
                },
              },
            },
      ),
    );
    action(
      'selection',
      async () => {
        try {
          await api(`/remediations/${proposal.id}`, 'PATCH', {
            selections: { [item.id]: selected },
          });
        } catch (error) {
          setCampaigns(previous);
          throw error;
        }
      },
      'Correction selection saved.',
    );
  }
  function apply() {
    action(
      'apply',
      () =>
        api(`/remediations/${proposal.id}/apply`, 'POST', { expected_version: campaign.version }),
      'Selected corrections saved as a new draft version.',
    );
  }
  function requestApproval() {
    action(
      'request',
      () =>
        api('/approvals', 'POST', {
          campaign_id: campaign.id,
          audit_id: audit.id,
          reviewer,
          comments: '',
        }),
      'Human review requested.',
    );
  }
  function reviewDecision(decision: string) {
    action(
      decision,
      async () => {
        await api(`/approvals/${review!.id}/${decision}`, 'POST', {
          reviewer,
          comments,
          language_reviewed: languageReviewed,
        });
        setReview(null);
      },
      decision === 'approve'
        ? 'Campaign approved for activation. No messages have been sent.'
        : 'Campaign rejected. Decision saved.',
    );
  }
  function editor(c?: Row) {
    setForm(
      c
        ? {
            ...c,
            recipient_ids: c.recipients.map((r: Row) => r.id),
            evidence_json: JSON.stringify(c.supporting_evidence, null, 2),
          }
        : {
            name: '',
            description: 'Synthetic campaign',
            channel: 'email',
            subject: '',
            marketing_content: '',
            target_audience: 'Synthetic learning community',
            language: 'fr',
            language_variants: {},
            supporting_evidence: [],
            recipient_ids: [],
            evidence_json: '[]',
          },
    );
  }
  function saveForm() {
    action(
      'save',
      async () => {
        const keys = [
          'name',
          'description',
          'channel',
          'subject',
          'marketing_content',
          'target_audience',
          'language',
          'language_variants',
          'recipient_ids',
        ];
        const body: Row = Object.fromEntries(keys.map((k) => [k, form![k]]));
        body.supporting_evidence = JSON.parse(form!.evidence_json);
        if (form!.id) body.expected_version = form!.version;
        const saved = await api(
          form!.id ? `/campaigns/${form!.id}` : '/campaigns',
          form!.id ? 'PATCH' : 'POST',
          body,
        );
        setSelected(saved.id);
        setForm(null);
      },
      'Campaign saved. A new audit is required after edits.',
    );
  }
  const blocking = audit?.findings.filter((f: Row) => f.blocking) || [];
  const current = audit?.status === 'completed' && audit.campaign_version === campaign?.version;
  const cleared = current && blocking.length === 0;
  const button = (
    label: string,
    onClick: () => void,
    disabled = false,
    secondary = false,
    Icon = ArrowRight,
  ) => (
    <button
      className={secondary ? 'btn secondary' : 'btn'}
      onClick={onClick}
      disabled={disabled || !!busy}
    >
      {busy && label.toLowerCase().includes(busy) ? (
        <Loader2 size={16} className="spin" />
      ) : (
        <Icon size={16} />
      )}{' '}
      {label}
    </button>
  );
  function campaignSelect() {
    return (
      <select
        aria-label="Selected campaign"
        className="campaign-select"
        value={campaign?.id || ''}
        onChange={(e) => {
          setSelected(Number(e.target.value));
          setFocusAudit(null);
        }}
      >
        {campaigns.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    );
  }
  function risk(a: Row | undefined, large = false) {
    const score = a?.status === 'completed' ? a.risk_score : null;
    return (
      <div
        className={'risk-ring ' + (large ? 'large' : '')}
        style={
          {
            '--score': score || 0,
            '--risk':
              score === null
                ? '#3b465e'
                : score >= 60
                  ? '#fb8768'
                  : score >= 25
                    ? '#f2c663'
                    : '#6de1bd',
          } as React.CSSProperties
        }
      >
        <div>
          <strong>{score ?? '—'}</strong>
          <span>{score === null ? 'NOT AUDITED' : '/ 100'}</span>
        </div>
      </div>
    );
  }
  function table(rows: Row[]) {
    return (
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>CAMPAIGN NAME</th>
              <th>CHANNEL</th>
              <th>AUDIENCE</th>
              <th>RISK</th>
              <th>STATUS</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td>
                  <button
                    className="campaign-link"
                    onClick={() => {
                      setSelected(c.id);
                      nav('/audit');
                    }}
                  >
                    <span className={'table-icon t' + c.id}>
                      <Megaphone size={17} />
                    </span>
                    <span>
                      {c.name}
                      <small>Synthetic campaign · Version {c.version}</small>
                    </span>
                  </button>
                </td>
                <td>
                  <span className="muted inline">
                    <Mail size={14} />
                    {human(c.channel)}
                  </span>
                </td>
                <td>
                  {c.recipient_count}
                  <span className="muted"> contacts</span>
                </td>
                <td>
                  <span
                    className={
                      'score-text ' + (c.latest_audit?.risk_score >= 60 ? 'coral' : 'mint')
                    }
                  >
                    {c.latest_audit?.status === 'completed' ? c.latest_audit.risk_score : '—'}
                  </span>
                </td>
                <td>
                  <Badge value={c.status} />
                </td>
                <td>
                  <button
                    className="icon-btn"
                    aria-label={'Edit ' + c.name}
                    onClick={() => editor(c)}
                  >
                    <Pencil size={15} />
                  </button>
                  <button
                    className="icon-btn"
                    aria-label={'Open ' + c.name}
                    onClick={() => {
                      setSelected(c.id);
                      nav('/audit');
                    }}
                  >
                    <ArrowUpRight size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <div className="empty">No campaigns match your selection.</div>}
      </div>
    );
  }
  function findings(a: Row | undefined) {
    return (
      <div className="findings-list">
        {a?.findings?.map((f: Row) => (
          <details className="finding" key={f.id} open={route === '/demo' || undefined}>
            <summary>
              <span className={'severity-dot ' + f.severity} />
              <div>
                <strong>{f.title}</strong>
                <span>
                  {f.agent_type} <i>·</i> {f.affected_count} affected <i>·</i> {f.rule_id}
                </span>
              </div>
              <Badge value={f.severity} />
              <ChevronDown size={15} />
            </summary>
            <div className="finding-body">
              <p>{f.explanation}</p>
              <div className="evidence">
                <Fingerprint size={15} />
                <code>
                  {f.evidence.quote
                    ? `“${f.evidence.quote}” · ${f.evidence.locale}`
                    : f.evidence.preferred_language
                      ? `${f.affected_count} contacts prefer ${f.evidence.preferred_language.toUpperCase()} · Available: ${f.evidence.available_languages.join(', ').toUpperCase()}`
                      : f.evidence.recipient_ids
                        ? `Stored recipient IDs: ${f.evidence.recipient_ids.join(', ')}`
                        : JSON.stringify(f.evidence)}
                </code>
              </div>
              <p className="recommendation">
                <WandSparkles size={14} />
                {f.recommendation}
              </p>
              <small>
                Risk contribution: +{f.risk_contribution} points{' '}
                {f.blocking ? '· Blocks approval' : ''}
                {f.evidence.reference ? ` · Supplied evidence: ${f.evidence.reference}` : ''}
              </small>
            </div>
          </details>
        ))}
        {!a?.findings?.length && (
          <div className="empty">
            <CheckCircle2 size={25} />
            <p>
              {a?.status === 'completed'
                ? 'No policy findings in this audited version.'
                : 'Run an audit to inspect campaign policy risks.'}
            </p>
          </div>
        )}
      </div>
    );
  }
  function agentsPanel(a: Row | undefined) {
    return (
      <div className="agent-pipeline">
        {agentInfo.map(([name, desc, Icon], i) => {
          const state = a?.agent_states?.[name as string] || 'waiting';
          const Comp = Icon as typeof Users;
          return (
            <React.Fragment key={name as string}>
              <div className={'agent ' + state}>
                <div className="agent-symbol">
                  <Comp size={23} />
                  <span>
                    {state === 'completed' ? (
                      <Check size={10} />
                    ) : state === 'running' ? (
                      <Loader2 className="spin" size={10} />
                    ) : (
                      <Circle size={8} />
                    )}
                  </span>
                </div>
                <strong>{name as string}</strong>
                <small>{desc as string}</small>
                <div className="agent-state">
                  {state === 'completed' ? (
                    <CheckCircle2 size={11} />
                  ) : state === 'running' ? (
                    <Loader2 className="spin" size={11} />
                  ) : (
                    <Circle size={9} />
                  )}{' '}
                  {human(state)}
                </div>
              </div>
              {i < 4 && <div className="agent-connector" />}
            </React.Fragment>
          );
        })}
      </div>
    );
  }
  function trail(events: Row[], limit = 10) {
    return (
      <div className="timeline">
        {events.slice(0, limit).map((e) => (
          <div className="timeline-item" key={e.id}>
            <span
              className={'timeline-node ' + (e.event_type === 'human_approved' ? 'mint' : '')}
            />
            <div>
              <strong>{human(e.event_type)}</strong>
              <p>
                {e.details.agent ||
                  e.details.reviewer ||
                  e.details.message ||
                  (e.details.version
                    ? `Campaign version ${e.details.version}`
                    : 'Persistent backend event')}
                {e.details.risk_score !== undefined ? ` · Risk ${e.details.risk_score}/100` : ''}
              </p>
            </div>
            <time>{date(e.timestamp)}</time>
          </div>
        ))}
        {!events.length && <p className="empty">No events recorded.</p>}
      </div>
    );
  }
  function remediationPanel() {
    return !proposal ? (
      <div className="panel empty">
        <WandSparkles size={34} />
        <h3>Every correction starts with evidence.</h3>
        <p>Run an audit, then prepare a reviewable remediation proposal.</p>
        {button('Generate Corrections', generate, !current, false, WandSparkles)}
      </div>
    ) : (
      <>
        <div className="section-heading">
          <div>
            <span className="eyebrow">REMEDIATION WORKSPACE</span>
            <h2>Better copy. A safer audience.</h2>
          </div>
          <Badge value={proposal.status} />
        </div>
        <div className="copy-grid">
          <div className="panel copy-panel">
            <div className="panel-label">
              <span className="severity-dot high" />
              Original · Audited v{audit.campaign_version}
            </div>
            <small className="copy-subject-label">SUBJECT</small>
            <CopyDiff
              original={audit.snapshot.subject}
              proposed={
                proposal.corrections.find((x: Row) => x.id === 'copy')?.proposed_subject ??
                audit.snapshot.subject
              }
              side="original"
            />
            <small className="copy-subject-label">MESSAGE</small>
            <CopyDiff
              original={proposal.original_content}
              proposed={proposal.proposed_content}
              side="original"
            />
          </div>
          <div className="panel copy-panel proposed">
            <div className="panel-label">
              <Sparkles size={15} />
              Proposed draft · Deterministic editorial correction
            </div>
            <small className="copy-subject-label">SUBJECT</small>
            <CopyDiff
              original={audit.snapshot.subject}
              proposed={
                proposal.corrections.find((x: Row) => x.id === 'copy')?.proposed_subject ??
                audit.snapshot.subject
              }
              side="proposed"
            />
            <small className="copy-subject-label">MESSAGE</small>
            <CopyDiff
              original={proposal.original_content}
              proposed={proposal.proposed_content}
              side="proposed"
            />
          </div>
        </div>
        <div className="panel correction-list">
          {proposal.corrections.map((item: Row) => (
            <label key={item.id} className="correction">
              <input
                type="checkbox"
                checked={item.selected}
                disabled={proposal.status === 'applied' || !!busy}
                onChange={() => chooseCorrection(item)}
              />
              <span>
                <strong>{item.title}</strong>
                <small>{item.description}</small>
              </span>
              <Badge value={item.selected ? 'accepted' : 'rejected'} />
            </label>
          ))}
          {!proposal.corrections.length && (
            <p>No automatic corrections are necessary. Review findings manually.</p>
          )}
        </div>
        {proposal.excluded_recipients.length > 0 && (
          <div className="notice">
            <Users size={18} />
            <span>
              <strong>{proposal.excluded_recipients.length} recipient exclusions</strong> ·{' '}
              {audit.snapshot.recipients.length} →{' '}
              {audit.snapshot.recipients.length - proposal.excluded_recipients.length} contacts if
              selected. Stored consent preferences remain intact.
              <details>
                <summary>Inspect recipient IDs</summary>
                {proposal.excluded_recipients.join(', ')}
              </details>
            </span>
          </div>
        )}
        {Object.entries(proposal.proposed_language_variants).map(([lang, text]) => (
          <div className="panel language-copy" key={lang}>
            <span className="eyebrow">
              {lang.toUpperCase()} LANGUAGE VARIANT · HUMAN REVIEW REQUIRED
            </span>
            <p lang={lang} dir={lang === 'ar' ? 'rtl' : 'ltr'}>
              {text as string}
            </p>
          </div>
        ))}
        <div className="action-row">
          {button(
            proposal.status === 'applied' ? 'Corrections Applied' : 'Apply Selected Corrections',
            apply,
            proposal.status === 'applied' || !proposal.corrections.some((x: Row) => x.selected),
            false,
            CheckCheck,
          )}
          {button(
            'Re-Audit Draft',
            runAudit,
            proposal.status !== 'applied' || running,
            true,
            ScanLine,
          )}
          {button(
            'Inspect / Restore Versions',
            () =>
              action(
                'versions',
                async () => setRevisions(await api(`/campaigns/${campaign.id}/revisions`)),
                '',
              ),
            false,
            true,
            History,
          )}
        </div>
      </>
    );
  }
  const globalDisabled = !!busy || !!running;
  return (
    <div className="app-shell">
      <aside className={'sidebar ' + (mobile ? 'open' : '')}>
        <a
          className="brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            nav('/');
          }}
        >
          <div className="brand-mark">
            <ShieldCheck size={25} />
          </div>
          <span>
            FAIRGATE<span className="brand-ai">AI</span>
            <small>CAMPAIGN INTELLIGENCE</small>
          </span>
        </a>
        <div className="workspace">
          <div className="workspace-avatar">IM</div>
          <div>
            <strong>IT-Minds Workspace</strong>
            <small>Enterprise prototype</small>
          </div>
          <ChevronDown size={13} />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {labels.map((label, i) => {
            const Icon = icons[i];
            return (
              <a
                href={paths[i]}
                className={(route === paths[i] ? 'active ' : '') + (i === 7 ? 'demo-nav' : '')}
                key={label}
                onClick={(e) => {
                  e.preventDefault();
                  nav(paths[i]);
                }}
              >
                <Icon size={18} />
                <span>{label}</span>
                {i === 4 && (dash?.approval_queue || 0) > 0 && <b>{dash?.approval_queue}</b>}
                {i === 7 && <ArrowUpRight size={14} />}
              </a>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="safe-mode">
            <span className="live-dot" />
            <strong>Safe by design</strong>
            <p>
              Human approval.
              <br />
              Always in the loop.
            </p>
            <ShieldCheck size={27} />
          </div>
          <div className="team">
            <div className="avatar">IM</div>
            <div>
              <strong>IT-Minds</strong>
              <small>Deloitte Hackathon · 2027</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="icon-btn mobile-menu"
            aria-label="Toggle navigation"
            onClick={() => setMobile(!mobile)}
          >
            <PanelLeftClose size={20} />
          </button>
          <span className="breadcrumb">
            Workspace <span>/</span> <strong>{labels[paths.indexOf(route)] || 'Overview'}</strong>
          </span>
          <div className="topbar-right">
            <span className="demo-pill">
              <span className="live-dot" />
              Demo Mode — Synthetic Data
            </span>
            <div className="top-divider" />
            <span className="reviewer-label">Local demo reviewer</span>
            <div className="avatar small">IM</div>
          </div>
        </header>
        <main>
          {error && (
            <div className="error-banner" role="alert">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button onClick={() => setError('')} aria-label="Dismiss error">
                <X size={17} />
              </button>
            </div>
          )}
          {!dash ? (
            <div className="loading">
              <Loader2 className="spin" size={30} />
              <p>Connecting to FAIRGATE…</p>
              {button(
                'Retry Connection',
                () => load().catch((e) => setError(e.message)),
                false,
                true,
              )}
            </div>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span className="live-dot" /> INDEPENDENT AI GOVERNANCE
                  </div>
                  <h1>
                    {route === '/demo'
                      ? 'When AI Audits AI.'
                      : route === '/'
                        ? 'Campaign confidence starts here.'
                        : labels[paths.indexOf(route)] || 'Overview'}
                  </h1>
                  <p>
                    {route === '/demo'
                      ? 'FAIRGATE AI · A complete, live preflight journey. Every decision leaves a trace.'
                      : route === '/'
                        ? 'A clear view of campaign risk. A human in control of every decision.'
                        : route === '/audit'
                          ? 'Five specialized agents. One transparent path to responsible marketing.'
                          : route === '/remediation'
                            ? 'Inspect every correction, preserve every version, verify every change.'
                            : route === '/governance'
                              ? 'Explicit policy gates. Traceable decisions. Accountable human review.'
                              : route === '/integrations'
                                ? 'A credible CRM boundary. Honest connection states. No message delivery.'
                                : 'Independent oversight across your campaign lifecycle.'}
                  </p>
                </div>
                <div className="heading-actions">
                  {route === '/' ? (
                    button('Launch Live Demo', () => nav('/demo'), false, false, Play)
                  ) : route === '/campaigns' ? (
                    button('Create Campaign', () => editor(), false, false, Plus)
                  ) : route === '/demo' ? (
                    <div className="action-row">
                      {button(
                        'Open Main Campaign',
                        () =>
                          setSelected(
                            campaigns.find((c) => c.name === 'Digital Future Morocco 2027')?.id ||
                              campaigns[0]?.id,
                          ),
                        false,
                        true,
                        Megaphone,
                      )}
                      {button('Reset Demo', () => setConfirm(true), false, true, RotateCcw)}
                    </div>
                  ) : (
                    campaignSelect()
                  )}
                </div>
              </div>
              {route === '/' && (
                <>
                  <div className="hero">
                    <div className="hero-copy">
                      <div className="hero-tag">
                        <Sparkles size={13} /> THE PREFLIGHT LAYER FOR AI MARKETING
                      </div>
                      <h2>
                        Move fast.
                        <br />
                        Keep your <em>guardrails.</em>
                      </h2>
                      <p>
                        Your AI creates the campaign. FAIRGATE independently
                        <br className="desktop-break" /> evaluates the risks before a human gives
                        the green light.
                      </p>
                      <div className="action-row">
                        {button(
                          'Open AI Audit Center',
                          () => nav('/audit'),
                          false,
                          false,
                          ScanLine,
                        )}
                        <span className="hero-note">
                          <LockKeyhole size={13} /> No automatic activation
                        </span>
                      </div>
                    </div>
                    <div className="hero-visual" aria-hidden="true">
                      <div className="orbit orbit-one" />
                      <div className="orbit orbit-two" />
                      <div className="orbit orbit-three" />
                      <div className="shield-core">
                        <ShieldCheck size={69} strokeWidth={1.2} />
                      </div>
                      <span className="float-chip chip-one">
                        <CheckCircle2 size={13} /> CONSENT GUARDIAN
                      </span>
                      <span className="float-chip chip-two">
                        <Fingerprint size={13} /> EVIDENCE REVIEW
                      </span>
                      <span className="float-chip chip-three">
                        <Users size={13} /> HUMAN GOVERNANCE
                      </span>
                      <span className="visual-caption">INDEPENDENT BY DESIGN</span>
                    </div>
                  </div>
                  <div className="metric-grid">
                    {[
                      [
                        Megaphone,
                        'Total campaigns',
                        dash.campaign_count,
                        'Synthetic CRM campaigns',
                      ],
                      [
                        ScanLine,
                        'Audits completed',
                        dash.audits_completed,
                        'Persistent, versioned results',
                      ],
                      [
                        AlertTriangle,
                        'Requiring attention',
                        dash.requiring_attention,
                        'Unresolved policy findings',
                      ],
                      [
                        FileCheck2,
                        'Approval queue',
                        dash.approval_queue,
                        'Awaiting a human decision',
                      ],
                    ].map(([Icon, title, value, sub], i) => {
                      const Comp = Icon as typeof Users;
                      return (
                        <div className="metric panel" key={String(title)}>
                          <div>
                            <span>{title as string}</span>
                            <Comp size={17} />
                          </div>
                          <strong>
                            {value as number}
                            <span className={'metric-accent m' + i} />
                          </strong>
                          <small>{sub as string}</small>
                        </div>
                      );
                    })}
                  </div>
                  <div className="dashboard-grid">
                    <section className="panel campaigns-panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Campaign watchlist</h2>
                          <p>Your latest campaigns, with risk in focus.</p>
                        </div>
                        <button className="text-button" onClick={() => nav('/campaigns')}>
                          View all <ArrowUpRight size={14} />
                        </button>
                      </div>
                      {table(campaigns)}
                    </section>
                    <section className="panel distribution">
                      <div className="panel-heading">
                        <div>
                          <h2>Risk distribution</h2>
                          <p>Latest completed campaign audits</p>
                        </div>
                        <Activity size={17} className="muted" />
                      </div>
                      {dash.risk_distribution.some((x: Row) => x.value) ? (
                        <div className="chart">
                          <ResponsiveContainer width="100%" height={180}>
                            <BarChart data={dash.risk_distribution} barSize={35}>
                              <XAxis
                                dataKey="name"
                                stroke="#8995aa"
                                tickLine={false}
                                axisLine={false}
                                fontSize={12}
                              />
                              <Tooltip
                                contentStyle={{
                                  background: '#182235',
                                  border: '1px solid #344159',
                                  borderRadius: 8,
                                }}
                                cursor={{ fill: '#ffffff05' }}
                              />
                              <Bar dataKey="value" radius={[5, 5, 0, 0]} isAnimationActive={false}>
                                {['#6de1bd', '#f2c663', '#fb8768'].map((color) => (
                                  <Cell key={color} fill={color} />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      ) : (
                        <div className="empty chart">
                          <ScanLine size={30} />
                          <p>Run your first audit to map risk.</p>
                        </div>
                      )}
                      <div className="chart-note">
                        Internal prototype indicator · not a certified compliance score
                      </div>
                    </section>
                  </div>
                  <div className="bottom-grid">
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Activity stream</h2>
                          <p>From the persistent audit trail.</p>
                        </div>
                        <span className="live-tag">
                          <span className="live-dot" />
                          LIVE DATA
                        </span>
                      </div>
                      {trail(dash.activity, 4)}
                    </section>
                    <section className="panel trust-panel">
                      <div className="trust-icon">
                        <Scale size={25} />
                      </div>
                      <span className="eyebrow">GOVERNANCE, BUILT IN</span>
                      <h2>
                        Approval is a decision.
                        <br />
                        Sending is a separate action.
                      </h2>
                      <p>
                        FAIRGATE prepares campaigns for activation. It never sends marketing
                        communications.
                      </p>
                      <button className="text-button" onClick={() => nav('/governance')}>
                        Explore governance <ArrowRight size={15} />
                      </button>
                    </section>
                  </div>
                </>
              )}
              {route === '/campaigns' && (
                <>
                  <div className="toolbar">
                    <div className="search-field">
                      <Search size={17} />
                      <input
                        placeholder="Search campaigns…"
                        aria-label="Search campaigns"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </div>
                    <select
                      aria-label="Filter campaign status"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    >
                      <option value="all">All statuses</option>
                      {[...new Set(campaigns.map((c) => c.status))].map((s) => (
                        <option key={s} value={s}>
                          {human(s)}
                        </option>
                      ))}
                    </select>
                    <span className="muted">{campaigns.length} campaigns · synthetic data</span>
                  </div>
                  <div className="panel">
                    {table(
                      campaigns.filter(
                        (c) =>
                          c.name.toLowerCase().includes(search.toLowerCase()) &&
                          (filter === 'all' || c.status === filter),
                      ),
                    )}
                  </div>
                </>
              )}
              {(route === '/audit' || route === '/demo') && campaign && (
                <>
                  <div className="campaign-banner panel">
                    <div className="campaign-banner-icon">
                      <Megaphone size={25} />
                    </div>
                    <div className="campaign-banner-text">
                      <span className="eyebrow">
                        {route === '/demo'
                          ? 'LIVE DEMO · SYNTHETIC CAMPAIGN'
                          : 'CAMPAIGN PREFLIGHT'}{' '}
                        · VERSION {campaign.version}
                      </span>
                      <h2>{campaign.name}</h2>
                      <div className="meta">
                        <span>
                          <Mail size={13} />
                          {human(campaign.channel)}
                        </span>
                        <span>
                          <Users size={13} />
                          {campaign.recipient_count} synthetic contacts
                        </span>
                        <span>
                          <Globe2 size={13} />
                          {[campaign.language, ...Object.keys(campaign.language_variants)]
                            .join(' + ')
                            .toUpperCase()}
                        </span>
                        <Badge value={campaign.status} />
                      </div>
                    </div>
                    {route === '/demo' &&
                      button(
                        'Review Findings',
                        () =>
                          document
                            .getElementById('campaign-findings')
                            ?.scrollIntoView({ behavior: 'smooth' }),
                        !current,
                        true,
                        Eye,
                      )}
                    {button(
                      running ? 'Auditing…' : 'Run Audit',
                      runAudit,
                      globalDisabled,
                      false,
                      ScanLine,
                    )}
                    <button
                      className="icon-btn"
                      title="Edit campaign"
                      onClick={() => editor(campaign)}
                    >
                      <Pencil size={17} />
                    </button>
                  </div>
                  {route === '/demo' && (
                    <div className="demo-steps">
                      {[
                        'Campaign',
                        'Audit',
                        'Corrections',
                        'Re-audit',
                        'Human review',
                        'Ready',
                      ].map((s, i) => (
                        <div
                          className={
                            i === 0 ||
                            (i === 1 && audit) ||
                            (i === 2 && (proposal || campaign.version > 1)) ||
                            (i === 3 && cleared) ||
                            (i === 4 &&
                              (pending || campaign.status === 'approved_for_activation')) ||
                            (i === 5 && campaign.status === 'approved_for_activation')
                              ? 'done'
                              : ''
                          }
                          key={s}
                        >
                          <span>{i + 1}</span>
                          {s}
                        </div>
                      ))}
                    </div>
                  )}
                  <section className="panel orchestration">
                    <div className="panel-heading">
                      <div>
                        <h2>
                          <span className="inline">
                            <ScanLine size={18} /> Agent orchestration
                          </span>
                        </h2>
                        <p>Real execution states · modular deterministic policy engine</p>
                      </div>
                      <Badge value={audit?.status || 'waiting'} />
                    </div>
                    {agentsPanel(audit)}
                    <div className="orchestration-footer">
                      <span>
                        <span className="live-dot" />{' '}
                        {running
                          ? 'Polling backend execution…'
                          : audit?.completed_at
                            ? `Completed ${date(audit.completed_at)}`
                            : 'Ready to evaluate campaign data'}
                      </span>
                      <span>
                        Deterministic baseline <span className="muted">/</span> No LLM required
                      </span>
                    </div>
                  </section>
                  <div className="audit-grid">
                    <section id="campaign-findings" className="panel findings-panel">
                      <div className="panel-heading">
                        <div>
                          <h2>
                            Findings & evidence{' '}
                            <span className="count">{audit?.findings?.length || 0}</span>
                          </h2>
                          <p>
                            {current
                              ? 'Results for the current draft.'
                              : audit
                                ? 'Campaign changed or audit is in progress. Re-audit before approval.'
                                : 'Evidence will appear after the first audit.'}
                          </p>
                        </div>
                        {button(
                          'Generate Corrections',
                          generate,
                          !current || !!proposal,
                          true,
                          WandSparkles,
                        )}
                      </div>
                      {findings(audit)}
                    </section>
                    <aside className="panel risk-panel">
                      <span className="eyebrow">INTERNAL RISK INDICATOR</span>
                      {risk(audit, true)}
                      <h3>
                        {!audit
                          ? 'Awaiting evaluation'
                          : running
                            ? 'Audit in progress'
                            : audit.risk_score >= 60
                              ? 'Review required'
                              : audit.risk_score
                                ? 'Improvements recommended'
                                : 'Policy checks passed'}
                      </h3>
                      <p>
                        Transparent findings. Explicit policy gates.
                        <br />
                        Human judgment stays essential.
                      </p>
                      <div className="risk-breakdown">
                        {['critical', 'high', 'medium', 'low'].map((s) => (
                          <div key={s}>
                            <span>
                              <i className={'severity-dot ' + s} />
                              {human(s)}
                            </span>
                            <strong>
                              {audit?.findings.filter((f: Row) => f.severity === s).length || 0}
                            </strong>
                          </div>
                        ))}
                      </div>
                      {before && audit?.id !== before.id && (
                        <div className="before-after">
                          <span>
                            Before <strong>{before.risk_score}</strong>
                          </span>
                          <ArrowRight size={17} />
                          <span>
                            After <strong className="mint">{audit.risk_score}</strong>
                          </span>
                        </div>
                      )}
                      <small>
                        Score = min(100, 35 × critical + 25 × high + 10 × medium + 5 × low). Policy
                        gates apply independently of score.
                      </small>
                    </aside>
                  </div>
                  {route === '/demo' && (
                    <>
                      <section className="demo-copy panel">
                        <div className="panel-label">
                          <Mail size={16} /> ACTUAL CAMPAIGN COPY · V{campaign.version}
                        </div>
                        <pre>{campaign.marketing_content}</pre>
                        <div className="meta">
                          <span>
                            {campaign.eligible_count} eligible of {campaign.recipient_count}{' '}
                            selected contacts
                          </span>
                          <span>Original copy preserved in version history</span>
                        </div>
                      </section>
                      <div className="demo-section">{remediationPanel()}</div>
                      <section className="panel demo-governance">
                        <div>
                          <span className="eyebrow">HUMAN ACCOUNTABILITY</span>
                          <h2>
                            {campaign.status === 'approved_for_activation'
                              ? 'Campaign Approved for Activation'
                              : 'Final decision. Human by design.'}
                          </h2>
                          <p>
                            {campaign.status === 'approved_for_activation'
                              ? 'No messages have been sent.'
                              : blocking.length
                                ? `${blocking.length} blocking findings must be resolved before approval.`
                                : 'Review the audited draft and language variants before making a decision.'}
                          </p>
                        </div>
                        <div className="action-row">
                          {button(
                            'Request Approval',
                            requestApproval,
                            !cleared || !!pending || campaign.status === 'approved_for_activation',
                            true,
                            FileCheck2,
                          )}
                          {button(
                            'Approve',
                            () => {
                              setReview(pending);
                              setLanguageReviewed(false);
                            },
                            !pending,
                            false,
                            Check,
                          )}
                          {button(
                            'View Audit Trail',
                            () =>
                              document
                                .getElementById('demo-trail')
                                ?.scrollIntoView({ behavior: 'smooth' }),
                            false,
                            true,
                            History,
                          )}
                        </div>
                      </section>
                      <section id="demo-trail" className="panel">
                        <div className="panel-heading">
                          <div>
                            <h2>Persistent audit trail</h2>
                            <p>Every finding, correction, version and human decision.</p>
                          </div>
                          <Fingerprint size={20} />
                        </div>
                        {trail(
                          history.events.filter((e: Row) => e.campaign_id === campaign.id),
                          30,
                        )}
                      </section>
                    </>
                  )}
                </>
              )}
              {route === '/remediation' && campaign && (
                <>
                  <div className="context-line">
                    <h2>{campaign.name}</h2>
                    <Badge value={'v' + campaign.version} />
                    {button('Run / Re-run Audit', runAudit, running, true, ScanLine)}
                  </div>
                  {remediationPanel()}
                  <section className="panel comparison">
                    <div className="panel-heading">
                      <div>
                        <h2>Before / after verification</h2>
                        <p>Only actual completed audit results are compared.</p>
                      </div>
                      <GitCompareArrows size={20} />
                    </div>
                    {before && audit?.status === 'completed' ? (
                      <>
                        <div className="comparison-values">
                          <div>
                            {risk(before)}
                            <span>First audit · v{before.campaign_version}</span>
                          </div>
                          <ArrowRight size={28} />
                          <div>
                            {risk(audit)}
                            <span>Latest audit · v{audit.campaign_version}</span>
                          </div>
                          <div>
                            <strong className="mint">
                              {
                                before.findings.filter(
                                  (f: Row) =>
                                    !audit.findings.some((x: Row) => x.rule_id === f.rule_id),
                                ).length
                              }
                            </strong>
                            <span>Resolved findings</span>
                          </div>
                          <div>
                            <strong>{audit.findings.length}</strong>
                            <span>Remaining findings</span>
                          </div>
                        </div>
                        <div className="resolved-rules">
                          {before.findings
                            .filter(
                              (f: Row) => !audit.findings.some((x: Row) => x.rule_id === f.rule_id),
                            )
                            .map((f: Row) => (
                              <span key={f.id}>
                                <CheckCircle2 size={14} />
                                {f.title}
                              </span>
                            ))}
                        </div>
                      </>
                    ) : (
                      <div className="empty">
                        Complete an audit and re-audit to compare the saved results.
                      </div>
                    )}
                  </section>
                </>
              )}
              {route === '/governance' && campaign && (
                <>
                  <section className={'panel governance-gate ' + (cleared ? 'clear' : '')}>
                    <div className="gate-icon">
                      {cleared ? <ShieldCheck size={32} /> : <LockKeyhole size={32} />}
                    </div>
                    <div>
                      <span className="eyebrow">
                        GOVERNANCE GATE · {campaign.name} · V{campaign.version}
                      </span>
                      <h2>
                        {campaign.status === 'approved_for_activation'
                          ? 'Campaign Approved for Activation'
                          : cleared
                            ? 'Ready for human review'
                            : 'Approval is blocked'}
                      </h2>
                      <p>
                        {!current
                          ? 'A completed audit of the current version is required.'
                          : blocking.length
                            ? blocking.map((f: Row) => f.title).join(' · ')
                            : 'No blocking policy violations remain. A human decision is still required.'}
                      </p>
                      <small>
                        No messages have been sent. Local reviewer identity is simulated, not
                        production authentication.
                      </small>
                    </div>
                    {button(
                      'Request Approval',
                      requestApproval,
                      !cleared || !!pending || campaign.status === 'approved_for_activation',
                      false,
                      FileCheck2,
                    )}
                  </section>
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Decision queue & history</h2>
                        <p>Approval always references a specific campaign version and audit.</p>
                      </div>
                      <Scale size={20} />
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>CAMPAIGN / AUDIT</th>
                            <th>VERSION</th>
                            <th>REVIEWER</th>
                            <th>DECISION</th>
                            <th>REVIEW</th>
                          </tr>
                        </thead>
                        <tbody>
                          {history.approvals.map((p: Row) => (
                            <tr key={p.id}>
                              <td>
                                {campaigns.find((c) => c.id === p.campaign_id)?.name}
                                <small>
                                  Audit #{p.audit_id} · {date(p.timestamp)}
                                </small>
                                {p.comments && <small>{p.comments}</small>}
                              </td>
                              <td>v{p.campaign_version}</td>
                              <td>
                                {p.reviewer}
                                <small>Local demo identity</small>
                              </td>
                              <td>
                                <Badge value={p.decision} />
                              </td>
                              <td>
                                {p.decision === 'pending' ? (
                                  <button
                                    className="btn secondary compact"
                                    onClick={() => {
                                      setReview(p);
                                      setComments('');
                                      setLanguageReviewed(false);
                                    }}
                                  >
                                    Review decision <ArrowRight size={14} />
                                  </button>
                                ) : (
                                  <CheckCircle2 size={17} className="muted" />
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {!history.approvals.length && (
                        <div className="empty">
                          <Scale size={26} />
                          <p>
                            No approval requests yet. Resolve blocking findings, re-audit, then
                            request human review.
                          </p>
                        </div>
                      )}
                    </div>
                  </section>
                  <div className="notice">
                    <Info size={18} />
                    <span>
                      Approvals are invalidated when the campaign changes or a new audit is
                      requested. No numerical risk threshold can bypass an explicit blocking policy
                      rule.
                    </span>
                  </div>
                </>
              )}
              {route === '/history' && (
                <>
                  <div className="history-grid">
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Versioned audit records</h2>
                          <p>Immutable snapshots and persisted findings.</p>
                        </div>
                        <span className="count">{history.audits.length}</span>
                      </div>
                      {history.audits.map((a: Row) => (
                        <button
                          className={'audit-record ' + (focusAudit?.id === a.id ? 'selected' : '')}
                          key={a.id}
                          onClick={() => setFocusAudit(a)}
                        >
                          {risk(a)}
                          <span>
                            <strong>{campaigns.find((c) => c.id === a.campaign_id)?.name}</strong>
                            <small>
                              Audit #{a.id} · Version {a.campaign_version} · {date(a.created_at)}
                            </small>
                          </span>
                          <Badge value={a.status} />
                          <ChevronDown size={16} />
                        </button>
                      ))}
                      {!history.audits.length && <div className="empty">No audits yet.</div>}
                    </section>
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>
                            {focusAudit ? `Audit #${focusAudit.id} evidence` : 'Recorded activity'}
                          </h2>
                          <p>
                            {focusAudit
                              ? `Version ${focusAudit.campaign_version} · ${focusAudit.findings.length} findings`
                              : 'Live from SQLite persistence'}
                          </p>
                        </div>
                      </div>
                      {focusAudit ? findings(focusAudit) : trail(history.events, 14)}
                    </section>
                  </div>
                </>
              )}
              {route === '/integrations' && integration && (
                <>
                  <div className="integration-grid">
                    <section className="panel connector">
                      <div className="connector-icon local">
                        <Users size={27} />
                      </div>
                      <Badge value="operational" />
                      <h2>Local CRM</h2>
                      <p>
                        Complete campaign governance with persistent, synthetic contacts. No
                        credentials required.
                      </p>
                      <div className="connector-state">
                        <CheckCircle2 size={16} />
                        Demo Mode — Synthetic Data
                      </div>
                      <small>
                        {contacts.length} synthetic contacts · {campaigns.length} campaigns
                      </small>
                    </section>
                    <section className="panel connector">
                      <div className="connector-icon salesforce">☁</div>
                      <Badge value={sfResult?.connected ? 'verified' : 'not_connected'} />
                      <h2>Salesforce CRM</h2>
                      <p>
                        OAuth client credentials adapter. Authorized Campaign and CampaignMember
                        reads; conservative consent mapping.
                      </p>
                      <div className="connector-state muted">
                        <Plug size={16} />
                        {sfResult?.connected
                          ? 'OAuth verified for this request'
                          : integration.salesforce.status}
                      </div>
                      {button(
                        'Test Connection',
                        () =>
                          action(
                            'connection',
                            async () =>
                              setSfResult(await api('/integrations/salesforce/test', 'POST')),
                            'Connection test complete.',
                          ),
                        !integration.salesforce.configured,
                        true,
                        Plug,
                      )}
                    </section>
                    <section className="panel connector">
                      <div className="connector-icon agentforce">
                        <Sparkles size={27} />
                      </div>
                      <Badge value="proposed" />
                      <h2>Agentforce action</h2>
                      <p>
                        Documented custom action contract for campaign audits. Requires an org,
                        Named Credential, and authenticated gateway.
                      </p>
                      <div className="connector-state muted">
                        <Info size={16} />
                        Proposed — not operational
                      </div>
                      <code>POST /api/campaigns/&#123;id&#125;/audits</code>
                    </section>
                  </div>
                  <section className="panel config-panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Connection configuration</h2>
                        <p>
                          Server-side environment variables only. Secrets never enter the browser
                          bundle.
                        </p>
                      </div>
                      <LockKeyhole size={22} />
                    </div>
                    <pre>{`APP_MODE=demo\nDATABASE_URL=sqlite:///./backend/fairgate.db\nSALESFORCE_INSTANCE_URL=https://your-domain.my.salesforce.com\nSALESFORCE_CLIENT_ID=<server-side only>\nSALESFORCE_CLIENT_SECRET=<server-side only>\nSALESFORCE_WRITE_ENABLED=false`}</pre>
                    <div className="notice">
                      <Info size={17} />
                      <span>
                        Connected mode requires a separate database and disables local demo
                        review/reset. Standard CRM Campaigns are not Marketing Cloud Journeys. See
                        docs/salesforce.md for custom object mapping and access boundaries.
                      </span>
                    </div>
                  </section>
                </>
              )}
            </>
          )}
          <footer>
            <span>
              <ShieldCheck size={13} /> FAIRGATE AI <span className="muted">/</span> When AI Audits
              AI
            </span>
            <span>
              Synthetic data only <i>·</i> No messages sent <i>·</i> IT-Minds 2027
            </span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={18} />
          {toast}
          <button aria-label="Dismiss notification" onClick={() => setToast('')}>
            <X size={14} />
          </button>
        </div>
      )}
      {busy && (
        <div className="working-indicator" role="status">
          <Loader2 className="spin" size={14} /> Saving backend state…
        </div>
      )}
      {confirm && (
        <div className="modal-backdrop">
          <section
            className="modal small-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reset-title"
          >
            <RotateCcw size={29} className="mint" />
            <h2 id="reset-title">Restore the synthetic demo?</h2>
            <p>
              This removes local campaign changes, audits, and decisions, then restores the original
              four synthetic campaigns.
            </p>
            <div className="action-row">
              {button('Cancel', () => setConfirm(false), false, true, X)}
              {button(
                'Reset Demo',
                () =>
                  action(
                    'reset',
                    async () => {
                      const r = await api('/demo/reset', 'POST');
                      setSelected(r.main_campaign_id);
                      setConfirm(false);
                      setFocusAudit(null);
                    },
                    'Original synthetic demonstration restored.',
                  ),
                false,
                false,
                RotateCcw,
              )}
            </div>
          </section>
        </div>
      )}
      {form && (
        <div className="modal-backdrop">
          <section
            className="modal editor"
            role="dialog"
            aria-modal="true"
            aria-labelledby="editor-title"
          >
            <div className="modal-heading">
              <div>
                <span className="eyebrow">PERSISTENT CAMPAIGN DRAFT</span>
                <h2 id="editor-title">{form.id ? 'Edit Campaign' : 'Create Campaign'}</h2>
              </div>
              <button className="icon-btn" aria-label="Close editor" onClick={() => setForm(null)}>
                <X size={20} />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                saveForm();
              }}
            >
              <div className="form-grid">
                {[
                  ['name', 'Campaign name'],
                  ['subject', 'Email subject'],
                  ['description', 'Description'],
                  ['target_audience', 'Audience description'],
                ].map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <input
                      required={key === 'name'}
                      maxLength={
                        key === 'name'
                          ? 160
                          : key === 'subject'
                            ? 250
                            : key === 'description'
                              ? 4000
                              : 500
                      }
                      value={form[key]}
                      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                    />
                  </label>
                ))}
                <label>
                  Channel
                  <select
                    value={form.channel}
                    onChange={(e) => setForm({ ...form, channel: e.target.value })}
                  >
                    <option value="email">Email</option>
                    <option value="sms">SMS · requires channel permission</option>
                  </select>
                </label>
                <label>
                  Primary language
                  <select
                    value={form.language}
                    onChange={(e) => setForm({ ...form, language: e.target.value })}
                  >
                    {['fr', 'en', 'ar'].map((l) => (
                      <option key={l} value={l}>
                        {l.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label>
                Campaign content
                <textarea
                  required
                  rows={5}
                  maxLength={20000}
                  value={form.marketing_content}
                  onChange={(e) => setForm({ ...form, marketing_content: e.target.value })}
                />
              </label>
              <details className="editor-details">
                <summary>Language variants & supplied claim evidence</summary>
                {['ar', 'fr', 'en']
                  .filter((l) => l !== form.language)
                  .map((l) => (
                    <label key={l}>
                      {l.toUpperCase()} variant
                      <textarea
                        rows={2}
                        maxLength={20000}
                        value={form.language_variants[l] || ''}
                        onChange={(e) => {
                          const variants = { ...form.language_variants };
                          if (e.target.value.trim()) variants[l] = e.target.value;
                          else delete variants[l];
                          setForm({ ...form, language_variants: variants });
                        }}
                      />
                    </label>
                  ))}
                <label>
                  Evidence JSON · claim, reference, verified
                  <textarea
                    rows={3}
                    value={form.evidence_json}
                    onChange={(e) => setForm({ ...form, evidence_json: e.target.value })}
                  />
                </label>
                <small>
                  Supplied evidence is user-attested. Unverified references require manual
                  verification.
                </small>
              </details>
              <div className="recipient-heading">
                <label>Target audience · {form.recipient_ids.length} selected</label>
                <button
                  type="button"
                  className="text-button"
                  onClick={() =>
                    setForm({
                      ...form,
                      recipient_ids: contacts
                        .filter((r) => r.marketing_email_consent === true)
                        .map((r) => r.id),
                    })
                  }
                >
                  Select eligible
                </button>
                <button
                  type="button"
                  className="text-button"
                  onClick={() =>
                    setForm({
                      ...form,
                      recipient_ids:
                        form.recipient_ids.length === contacts.length
                          ? []
                          : contacts.map((r) => r.id),
                    })
                  }
                >
                  Toggle all
                </button>
              </div>
              <div className="recipient-list">
                {contacts.map((r) => (
                  <label key={r.id}>
                    <input
                      type="checkbox"
                      checked={form.recipient_ids.includes(r.id)}
                      onChange={() =>
                        setForm({
                          ...form,
                          recipient_ids: form.recipient_ids.includes(r.id)
                            ? form.recipient_ids.filter((id: number) => id !== r.id)
                            : [...form.recipient_ids, r.id],
                        })
                      }
                    />
                    <span>
                      {r.name}
                      <small>{r.preferred_language.toUpperCase()}</small>
                    </span>
                    <Badge
                      value={
                        r.marketing_email_consent === true
                          ? 'eligible'
                          : r.marketing_email_consent === false
                            ? 'opted_out'
                            : 'unknown'
                      }
                    />
                  </label>
                ))}
              </div>
              <div className="notice">
                <Info size={15} />
                <small>
                  Saving creates a new version and invalidates previous audit approval. All selected
                  contacts are evaluated by the consent agent.
                </small>
              </div>
              <button type="submit" className="btn" disabled={!!busy}>
                <Check size={17} />
                Save Campaign
              </button>
            </form>
          </section>
        </div>
      )}
      {review && (
        <div className="modal-backdrop">
          <section
            className="modal small-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="review-title"
          >
            <div className="modal-heading">
              <Scale size={27} className="mint" />
              <button
                className="icon-btn"
                aria-label="Close review"
                onClick={() => setReview(null)}
              >
                <X size={19} />
              </button>
            </div>
            <h2 id="review-title">Human approval</h2>
            <p>
              {campaigns.find((c) => c.id === review.campaign_id)?.name}
              <br />
              Audit #{review.audit_id} · Campaign version {review.campaign_version}
            </p>
            <label>
              Reviewer · simulated local identity
              <input
                value={reviewer}
                required
                maxLength={120}
                onChange={(e) => setReviewer(e.target.value)}
              />
            </label>
            <label>
              Decision comments
              <textarea
                rows={3}
                maxLength={4000}
                value={comments}
                onChange={(e) => setComments(e.target.value)}
              />
            </label>
            <label className="check-label">
              <input
                type="checkbox"
                checked={languageReviewed}
                onChange={(e) => setLanguageReviewed(e.target.checked)}
              />
              <span>I have reviewed the campaign, recipient changes, and language variants.</span>
            </label>
            <div className="notice">
              <Info size={16} />
              <small>Approval marks this version ready for activation. No messages are sent.</small>
            </div>
            <div className="action-row">
              {button('Reject', () => reviewDecision('reject'), !reviewer.trim(), true, Ban)}
              {button(
                'Approve',
                () => reviewDecision('approve'),
                !languageReviewed || !reviewer.trim(),
                false,
                Check,
              )}
            </div>
          </section>
        </div>
      )}
      {revisions && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="revisions-title"
          >
            <div className="modal-heading">
              <h2 id="revisions-title">Campaign version history</h2>
              <button
                className="icon-btn"
                aria-label="Close version history"
                onClick={() => setRevisions(null)}
              >
                <X size={20} />
              </button>
            </div>
            <p>
              Restore any earlier state into a new draft version. Audits and original data remain
              traceable.
            </p>
            {revisions.map((r) => (
              <details className="revision" key={r.id}>
                <summary>
                  Version {r.version} · {date(r.created_at)} · {r.snapshot.recipients.length}{' '}
                  contacts
                </summary>
                <pre>{r.snapshot.marketing_content}</pre>
                {button(
                  'Restore This Version',
                  () =>
                    action(
                      'restore',
                      async () => {
                        await api(
                          `/campaigns/${campaign.id}/revisions/${r.version}/restore`,
                          'POST',
                          { expected_version: campaign.version },
                        );
                        setRevisions(null);
                      },
                      'Version restored into a new draft.',
                    ),
                  r.version === campaign.version,
                  true,
                  RotateCcw,
                )}
              </details>
            ))}
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById('root')!).render(<App />);

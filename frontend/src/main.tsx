import { useEffect, useMemo, useState, type ComponentType, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import axios from 'axios';
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Database,
  Home,
  LogOut,
  Menu,
  MessageSquare,
  PackageSearch,
  RefreshCcw,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Truck,
  UserRound,
  Workflow,
} from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const client = axios.create({ baseURL: API });

type Tab = 'home' | 'chat' | 'orders' | 'refunds' | 'knowledge' | 'metrics' | 'escalations';
type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
  agent?: string;
  intent?: string;
  rag_sources?: string[];
  trace_id?: string;
  safety_report?: any;
};
type NavItem = { id: Tab; label: string; description: string; icon: ComponentType<{ size?: number }> };

const navItems: NavItem[] = [
  { id: 'home', label: 'Home', description: '运行总览', icon: Home },
  { id: 'chat', label: 'Chat', description: '多 Agent 对话', icon: MessageSquare },
  { id: 'orders', label: 'Orders & Logistics', description: '订单与物流', icon: PackageSearch },
  { id: 'refunds', label: 'Refunds', description: '退款审核', icon: RotateCcw },
  { id: 'knowledge', label: 'Knowledge/RAG', description: '规则与案例', icon: BookOpen },
  { id: 'metrics', label: 'Metrics & Safety', description: '指标与安全', icon: ShieldCheck },
  { id: 'escalations', label: 'Escalations', description: '人工升级', icon: AlertTriangle },
];

function App() {
  const [entered, setEntered] = useState(() => window.localStorage.getItem('agentic-cs-entered') === 'true');
  const [tab, setTab] = useState<Tab>('home');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  function enterApp() {
    window.localStorage.setItem('agentic-cs-entered', 'true');
    setEntered(true);
    setTab('home');
  }

  function exitApp() {
    window.localStorage.removeItem('agentic-cs-entered');
    setEntered(false);
    setTab('home');
  }

  if (!entered) {
    return <LandingPage onEnter={enterApp} />;
  }

  return (
    <div className="appShell">
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="brand">
          <div className="brandMark"><Bot size={20} /></div>
          <div>
            <strong>Agentic CS</strong>
            <span>Supabase-backed demo</span>
          </div>
        </div>
        <nav className="navList">
          {navItems.map(item => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={tab === item.id ? 'navItem active' : 'navItem'}
                onClick={() => {
                  setTab(item.id);
                  setSidebarOpen(false);
                }}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebarMeta">
          <StatusPill tone="success" label="Server DB" />
          <small>React to FastAPI to Supabase/Postgres</small>
        </div>
        <AccountMenu onExit={exitApp} />
      </aside>
      <main className="workspace">
        <div className="mobileTopbar">
          <button className="iconButton" onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
          <strong>{navItems.find(item => item.id === tab)?.label}</strong>
        </div>
        <button className={`scrim ${sidebarOpen ? 'show' : ''}`} onClick={() => setSidebarOpen(false)} aria-label="Close navigation" />
        <section className="content">
          {tab === 'home' && <HomeDashboard />}
          {tab === 'chat' && <Chat />}
          {tab === 'orders' && <OrdersAndLogistics />}
          {tab === 'refunds' && <Refunds />}
          {tab === 'knowledge' && <Knowledge />}
          {tab === 'metrics' && <MetricsSafety />}
          {tab === 'escalations' && <Escalations />}
        </section>
      </main>
    </div>
  );
}

function LandingPage({ onEnter }: { onEnter: () => void }) {
  return (
    <main className="landing">
      <div className="landingOverlay" />
      <nav className="landingNav">
        <div className="brand inverse">
          <div className="brandMark"><Bot size={20} /></div>
          <div>
            <strong>Agentic CS Console</strong>
            <span>CA6123 Group 5</span>
          </div>
        </div>
        <button className="secondaryButton" onClick={onEnter}>Enter demo</button>
      </nav>
      <div className="landingGrid">
        <div className="heroCopy">
          <span className="eyebrow"><Sparkles size={16} /> Responsible Multi-Agent Service</span>
          <h1>Agentic CS Console</h1>
          <p>
            A working customer-service control room for routing, RAG policy retrieval,
            safety guardrails, Supabase-backed sessions, and human escalation review.
          </p>
          <div className="heroActions">
            <button className="primaryButton" onClick={onEnter}><Workflow size={18} /> Open console</button>
            <span>Demo account mode. No client-side Supabase keys.</span>
          </div>
          <div className="heroStats">
            <MetricMini label="Agents" value="5" />
            <MetricMini label="RAG v2" value="Live" />
            <MetricMini label="HITL" value="Ready" />
          </div>
        </div>
        <div className="heroPreview" aria-label="System preview">
          <div className="previewHeader">
            <span />
            <span />
            <span />
            <strong>Live routing trace</strong>
          </div>
          <div className="previewBody">
            <PreviewStep label="Input guardrail" value="PII redacted" tone="success" />
            <PreviewStep label="RouterAgent" value="refund / 0.87" tone="info" />
            <PreviewStep label="RAG policy" value="3 sources" tone="info" />
            <PreviewStep label="QualitySafetyAgent" value="human review" tone="warning" />
          </div>
        </div>
      </div>
    </main>
  );
}

function HomeDashboard() {
  const { data, loading, error, refresh } = useApiData<any>('/api/admin/dashboard');
  const metrics = data?.metrics || {};

  return (
    <div className="page">
      <PageHeader
        icon={Home}
        title="Home Dashboard"
        subtitle="Project-wide operating view powered by the backend database connection."
        action={<button onClick={refresh}><RefreshCcw size={16} /> Refresh</button>}
      />
      {loading && <LoadingState />}
      {error && <ErrorState message={error} />}
      {data && (
        <>
          <div className="metricGrid">
            <MetricCard label="Messages" value={metrics.total_messages ?? 0} note="stored chat turns" />
            <MetricCard label="Sessions" value={metrics.total_sessions ?? 0} note="active customer context" />
            <MetricCard label="Escalations" value={metrics.open_escalations ?? 0} note="open human queue" tone="warning" />
            <MetricCard label="RAG hit rate" value={`${metrics.rag_hit_rate ?? 0}%`} note="assistant messages" tone="success" />
          </div>

          <div className="dashboardGrid">
            <Panel title="Agent Status" icon={Workflow}>
              <div className="agentList">
                {data.agent_status.map((agent: any) => (
                  <div className="agentRow" key={agent.agent}>
                    <span><CircleDot size={14} /> {agent.agent}</span>
                    <strong>{agent.calls}</strong>
                    <StatusPill tone={agent.status === 'active' ? 'success' : 'neutral'} label={agent.status} />
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="Database Path" icon={Database}>
              <div className="dbPath">
                <strong>{data.database.label}</strong>
                <p>Frontend calls FastAPI. FastAPI writes through SQLAlchemy to the configured DATABASE_URL.</p>
                <StatusPill tone="success" label="No frontend Supabase key" />
              </div>
            </Panel>
          </div>

          <div className="threeColumn">
            <Panel title="Recent Sessions" icon={MessageSquare}>
              <CompactList
                items={data.recent_sessions}
                empty="No sessions yet."
                render={(item: any) => (
                  <>
                    <strong>{item.id}</strong>
                    <span>{item.last_agent || 'router'} / {item.last_intent || 'unknown'} · {item.message_count} messages</span>
                  </>
                )}
              />
            </Panel>
            <Panel title="Recent Orders" icon={PackageSearch}>
              <CompactList
                items={data.recent_orders}
                empty="No orders yet."
                render={(item: any) => (
                  <>
                    <strong>{item.order_id}</strong>
                    <span>{item.status} · {formatMoney(item.total_amount)}</span>
                  </>
                )}
              />
            </Panel>
            <Panel title="Open Escalations" icon={AlertTriangle}>
              <CompactList
                items={data.open_escalations}
                empty="No open escalations."
                render={(item: any) => (
                  <>
                    <strong>{item.emotion_level}</strong>
                    <span>{truncate(item.escalation_reason || item.content, 86)}</span>
                  </>
                )}
              />
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

function Chat() {
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [input, setInput] = useState('我想查订单202404250001');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  const samplePrompts = [
    '那物流到哪里了？',
    '7天无理由退款规则是什么？',
    '订单202404250002 我要退款，质量有问题',
    '我要投诉，你们服务太差了，我要找经理',
  ];

  async function send(override?: string) {
    const content = (override ?? input).trim();
    if (!content || loading) return;
    setMessages(prev => [...prev, { role: 'user', content }]);
    setInput('');
    setLoading(true);
    try {
      const res = await client.post('/api/chat', { session_id: sessionId, message: content });
      setSessionId(res.data.session_id);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.response,
        agent: res.data.agent,
        intent: res.data.intent,
        rag_sources: res.data.rag_sources,
        trace_id: res.data.trace_id,
        safety_report: res.data.safety_report,
      }]);
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Request failed. Please check the backend API and try again.',
        agent: 'frontend',
        intent: 'error',
      }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page fullHeight">
      <PageHeader
        icon={MessageSquare}
        title="Chat"
        subtitle="Customer-facing conversation with router, RAG, trace, and safety metadata."
        badge={sessionId ? `Session ${sessionId}` : 'New session'}
      />
      <div className="chatLayout">
        <div className="chatSurface">
          <div className="messageStream">
            {messages.length === 0 && (
              <div className="emptyChat">
                <Bot size={34} />
                <strong>Start a service conversation</strong>
                <span>Try an order lookup first, then ask a follow-up logistics question.</span>
              </div>
            )}
            {messages.map((message, index) => <ChatBubble key={`${message.role}-${index}`} message={message} />)}
            {loading && <div className="message assistant">Processing...</div>}
          </div>
          <div className="promptRow">
            {samplePrompts.map(prompt => (
              <button className="promptChip" key={prompt} onClick={() => send(prompt)}>{prompt}</button>
            ))}
          </div>
          <div className="composer">
            <input
              value={input}
              onChange={event => setInput(event.target.value)}
              onKeyDown={event => event.key === 'Enter' && send()}
              placeholder="Ask about orders, logistics, refunds, complaints..."
            />
            <button onClick={() => send()} disabled={loading || !input.trim()}><Send size={18} /> Send</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function OrdersAndLogistics() {
  const [status, setStatus] = useState('all');
  const [orderId, setOrderId] = useState('202404250001');
  const [lookup, setLookup] = useState<any>(null);
  const [lookupError, setLookupError] = useState('');
  const path = `/api/admin/orders?limit=50${status === 'all' ? '' : `&status=${encodeURIComponent(status)}`}`;
  const { data, loading, error, refresh } = useApiData<any[]>(path);

  async function loadOrder() {
    setLookupError('');
    try {
      const res = await client.get(`/api/orders/${orderId}`);
      setLookup(res.data);
    } catch {
      setLookup(null);
      setLookupError('Order not found.');
    }
  }

  return (
    <div className="page">
      <PageHeader
        icon={Truck}
        title="Orders & Logistics"
        subtitle="Search order detail and monitor shipment state from the unified backend database."
        action={<button onClick={refresh}><RefreshCcw size={16} /> Refresh</button>}
      />
      <div className="toolBand">
        <label>
          Status
          <select value={status} onChange={event => setStatus(event.target.value)}>
            <option value="all">All</option>
            <option value="pending">pending</option>
            <option value="shipped">shipped</option>
            <option value="completed">completed</option>
            <option value="cancelled">cancelled</option>
          </select>
        </label>
        <label className="lookupField">
          Order lookup
          <span>
            <input value={orderId} onChange={event => setOrderId(event.target.value)} />
            <button onClick={loadOrder}><Search size={16} /> Search</button>
          </span>
        </label>
      </div>
      {lookupError && <ErrorState message={lookupError} />}
      {lookup && (
        <Panel title={`Order ${lookup.order_id}`} icon={PackageSearch}>
          <div className="detailGrid">
            <Detail label="Status" value={lookup.status} />
            <Detail label="Payment" value={lookup.payment_status} />
            <Detail label="Amount" value={formatMoney(lookup.total_amount)} />
            <Detail label="Customer" value={`${lookup.customer?.name || 'n/a'} / ${lookup.customer?.member_level || 'n/a'}`} />
          </div>
        </Panel>
      )}
      {loading && <LoadingState />}
      {error && <ErrorState message={error} />}
      <div className="dataList">
        {(data || []).map(order => (
          <div className="dataRow" key={order.order_id}>
            <div>
              <strong>{order.order_id}</strong>
              <span>{order.items?.[0]?.product_name || 'No item'} · {order.customer?.member_level || 'standard'}</span>
            </div>
            <div>
              <span>{order.shipment?.carrier_name || 'No shipment'}</span>
              <small>{order.shipment?.tracking_number || 'n/a'}</small>
            </div>
            <strong>{formatMoney(order.total_amount)}</strong>
            <StatusPill tone={order.status === 'completed' ? 'success' : order.status === 'shipped' ? 'info' : 'neutral'} label={order.status} />
          </div>
        ))}
      </div>
    </div>
  );
}

function Refunds() {
  const [status, setStatus] = useState('all');
  const path = `/api/admin/refunds?limit=50${status === 'all' ? '' : `&status=${encodeURIComponent(status)}`}`;
  const { data, loading, error, refresh } = useApiData<any[]>(path);

  return (
    <div className="page">
      <PageHeader
        icon={RotateCcw}
        title="Refunds"
        subtitle="Refund applications created by RefundAgent and stored through the backend database."
        action={<button onClick={refresh}><RefreshCcw size={16} /> Refresh</button>}
      />
      <div className="toolBand">
        <label>
          Status
          <select value={status} onChange={event => setStatus(event.target.value)}>
            <option value="all">All</option>
            <option value="pending">pending</option>
            <option value="approved">approved</option>
            <option value="rejected">rejected</option>
            <option value="completed">completed</option>
          </select>
        </label>
      </div>
      {loading && <LoadingState />}
      {error && <ErrorState message={error} />}
      <div className="dataList">
        {(data || []).map(refund => (
          <div className="dataRow" key={refund.id}>
            <div>
              <strong>Refund #{refund.id}</strong>
              <span>{refund.reason} · {refund.order?.order_id || 'n/a'}</span>
            </div>
            <div>
              <span>{refund.order?.customer?.name || 'Customer'}</span>
              <small>{formatDate(refund.created_at)}</small>
            </div>
            <strong>{formatMoney(refund.amount)}</strong>
            <StatusPill tone={refund.status === 'pending' ? 'warning' : 'success'} label={refund.status} />
          </div>
        ))}
        {!loading && data?.length === 0 && <EmptyState text="No refund records yet. Create one through Chat." />}
      </div>
    </div>
  );
}

function Knowledge() {
  const { data, loading, error, refresh } = useApiData<any>('/api/admin/shared-knowledge');
  return (
    <div className="page">
      <PageHeader
        icon={BookOpen}
        title="Knowledge/RAG"
        subtitle="RAG-v2 policy rules and historical cases used by specialist agents."
        action={<button onClick={refresh}><RefreshCcw size={16} /> Refresh</button>}
      />
      {loading && <LoadingState />}
      {error && <ErrorState message={error} />}
      {data && (
        <div className="knowledgeGrid">
          <Panel title={`Policy Rules (${data.policy_rules.length})`} icon={ShieldCheck}>
            <div className="stack">
              {data.policy_rules.map((rule: any) => (
                <div className="knowledgeItem" key={rule.rule_id}>
                  <strong>{rule.title}</strong>
                  <span>{rule.category} · {rule.decision} · {rule.rule_version}</span>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title={`Historical Cases (${data.historical_cases.length})`} icon={BookOpen}>
            <div className="stack">
              {data.historical_cases.map((item: any) => (
                <div className="knowledgeItem" key={item.case_id}>
                  <strong>{item.title}</strong>
                  <span>{item.category} · {item.outcome} · {item.customer_segment}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}

function MetricsSafety() {
  const { data: metrics, loading: metricsLoading, error: metricsError, refresh: refreshMetrics } = useApiData<any>('/api/admin/metrics');
  const { data: safety, loading: safetyLoading, error: safetyError, refresh: refreshSafety } = useApiData<any>('/api/admin/evaluation/safety');

  return (
    <div className="page">
      <PageHeader
        icon={BarChart3}
        title="Metrics & Safety"
        subtitle="Operational metrics and Responsible AI evaluation results."
        action={<button onClick={() => { refreshMetrics(); refreshSafety(); }}><RefreshCcw size={16} /> Refresh</button>}
      />
      {(metricsLoading || safetyLoading) && <LoadingState />}
      {(metricsError || safetyError) && <ErrorState message={metricsError || safetyError || 'Unable to load metrics.'} />}
      {metrics && (
        <div className="metricGrid">
          <MetricCard label="Total messages" value={metrics.total_messages ?? 0} note="stored turns" />
          <MetricCard label="Intent types" value={Object.keys(metrics.intent_distribution || {}).length} note="observed routes" />
          <MetricCard label="Agent calls" value={sumValues(metrics.agent_calls)} note="tool calls" />
          <MetricCard label="RAG hit rate" value={`${metrics.rag_hit_rate ?? 0}%`} note="knowledge use" tone="success" />
        </div>
      )}
      {safety && (
        <Panel title={`QualitySafetyAgent Evaluation · Overall ${safety.overall_pass_rate}%`} icon={ShieldCheck}>
          <div className="safetyGrid">
            {Object.entries(safety.summary).map(([name, value]) => {
              const metric = value as any;
              return (
                <div className="safetyItem" key={name}>
                  <span>{name.replace(/_/g, ' ')}</span>
                  <strong>{metric.rate}%</strong>
                  <small>{metric.passed}/{metric.total} passed</small>
                </div>
              );
            })}
          </div>
        </Panel>
      )}
      {metrics && <pre className="jsonPanel">{JSON.stringify(metrics, null, 2)}</pre>}
    </div>
  );
}

function Escalations() {
  const { data, loading, error, refresh } = useApiData<any[]>('/api/admin/escalations');
  const [busyId, setBusyId] = useState<number | null>(null);

  async function resolve(id: number) {
    setBusyId(id);
    try {
      await client.post(`/api/admin/escalations/${id}/resolve`, { note: 'resolved from UI demo' });
      refresh();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page">
      <PageHeader
        icon={AlertTriangle}
        title="Escalations"
        subtitle="Human-in-the-loop queue created by complaint, safety, refund, and logistics rules."
        action={<button onClick={refresh}><RefreshCcw size={16} /> Refresh</button>}
      />
      {loading && <LoadingState />}
      {error && <ErrorState message={error} />}
      <div className="dataList">
        {(data || []).map(item => (
          <div className="dataRow escalationRow" key={item.id}>
            <div>
              <strong>{item.emotion_level} · Session {item.session_id}</strong>
              <span>{truncate(item.content, 120)}</span>
              <small>{item.escalation_reason || 'manual review required'}</small>
            </div>
            <StatusPill tone="warning" label={item.status} />
            <button onClick={() => resolve(item.id)} disabled={busyId === item.id}>
              <CheckCircle2 size={16} /> Resolve
            </button>
          </div>
        ))}
        {!loading && data?.length === 0 && <EmptyState text="No open escalations." />}
      </div>
    </div>
  );
}

function AccountMenu({ onExit }: { onExit: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="accountBox">
      {open && (
        <div className="accountMenu">
          <button><Database size={16} /> Backend-managed Supabase</button>
          <button><ShieldCheck size={16} /> Demo account mode</button>
          <button onClick={onExit}><LogOut size={16} /> Back to landing</button>
        </div>
      )}
      <button className="accountButton" onClick={() => setOpen(value => !value)}>
        <span className="avatar"><UserRound size={18} /></span>
        <span>
          <strong>Huajian Demo</strong>
          <small>Operator</small>
        </span>
        <ChevronDown size={16} />
      </button>
    </div>
  );
}

function PageHeader({
  icon: Icon,
  title,
  subtitle,
  action,
  badge,
}: {
  icon: ComponentType<{ size?: number }>;
  title: string;
  subtitle: string;
  action?: ReactNode;
  badge?: string;
}) {
  return (
    <header className="pageHeader">
      <div className="pageTitleIcon"><Icon size={22} /></div>
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      {badge && <StatusPill tone="info" label={badge} />}
      {action && <div className="headerAction">{action}</div>}
    </header>
  );
}

function Panel({ title, icon: Icon, children }: { title: string; icon: ComponentType<{ size?: number }>; children: ReactNode }) {
  return (
    <section className="panel">
      <div className="panelHeader"><Icon size={18} /><strong>{title}</strong></div>
      {children}
    </section>
  );
}

function MetricCard({ label, value, note, tone = 'info' }: { label: string; value: string | number; note: string; tone?: 'info' | 'success' | 'warning' }) {
  return (
    <div className={`metricCard ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}

function MetricMini({ label, value }: { label: string; value: string }) {
  return (
    <div className="metricMini">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function PreviewStep({ label, value, tone }: { label: string; value: string; tone: 'success' | 'info' | 'warning' }) {
  return (
    <div className="previewStep">
      <span>{label}</span>
      <StatusPill tone={tone} label={value} />
    </div>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  return (
    <div className={`message ${message.role}`}>
      <p>{message.content}</p>
      {message.role === 'assistant' && (
        <div className="messageMeta">
          <StatusPill tone="info" label={message.agent || 'assistant'} />
          <StatusPill tone="neutral" label={message.intent || 'unknown'} />
          {message.trace_id && <span>Trace {message.trace_id}</span>}
          {message.rag_sources?.length ? <span>RAG {message.rag_sources.join(', ')}</span> : <span>RAG none</span>}
          {message.safety_report?.input?.blocked && <StatusPill tone="danger" label="Blocked" />}
          {message.safety_report?.input?.pii_redacted && <StatusPill tone="success" label="Input PII redacted" />}
          {message.safety_report?.output?.pii_redacted && <StatusPill tone="success" label="Output PII redacted" />}
        </div>
      )}
    </div>
  );
}

function StatusPill({ tone, label }: { tone: 'success' | 'warning' | 'danger' | 'info' | 'neutral'; label: string }) {
  return <span className={`statusPill ${tone}`}>{label}</span>;
}

function Detail({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="detail">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function CompactList({ items, empty, render }: { items: any[]; empty: string; render: (item: any) => ReactNode }) {
  if (!items?.length) return <EmptyState text={empty} />;
  return (
    <div className="compactList">
      {items.map((item, index) => <div className="compactItem" key={item.id || item.order_id || index}>{render(item)}</div>)}
    </div>
  );
}

function LoadingState() {
  return <div className="stateLine">Loading data...</div>;
}

function ErrorState({ message }: { message: string }) {
  return <div className="stateLine errorState">{message}</div>;
}

function EmptyState({ text }: { text: string }) {
  return <div className="emptyState">{text}</div>;
}

function useApiData<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError('');
    client.get(path)
      .then(response => {
        if (alive) setData(response.data);
      })
      .catch(() => {
        if (alive) setError(`Unable to load ${path}`);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [path, tick]);

  return useMemo(() => ({
    data,
    loading,
    error,
    refresh: () => setTick(value => value + 1),
  }), [data, loading, error]);
}

function formatMoney(value: number | string | null | undefined) {
  const numeric = Number(value || 0);
  return `¥${numeric.toFixed(2)}`;
}

function formatDate(value: string | null | undefined) {
  if (!value) return 'n/a';
  return new Date(value).toLocaleString('zh-CN', { hour12: false });
}

function truncate(value: string, length: number) {
  return value.length > length ? `${value.slice(0, length - 1)}...` : value;
}

function sumValues(input: Record<string, number> | undefined) {
  return Object.values(input || {}).reduce((sum, value) => sum + Number(value || 0), 0);
}

createRoot(document.getElementById('root')!).render(<App />);

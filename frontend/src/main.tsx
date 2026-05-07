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
  Home,
  Languages,
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
} from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const client = axios.create({ baseURL: API });

type Lang = 'zh' | 'en';
type Tab = 'home' | 'chat' | 'orders' | 'refunds' | 'knowledge' | 'metrics' | 'escalations';
type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral';
type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  safety_report?: any;
};
type NavItem = { id: Tab; icon: ComponentType<{ size?: number }> };

const navItems: NavItem[] = [
  { id: 'home', icon: Home },
  { id: 'chat', icon: MessageSquare },
  { id: 'orders', icon: PackageSearch },
  { id: 'refunds', icon: RotateCcw },
  { id: 'knowledge', icon: BookOpen },
  { id: 'metrics', icon: ShieldCheck },
  { id: 'escalations', icon: AlertTriangle },
];

const i18n = {
  zh: {
    nav: {
      home: '首页',
      chat: '在线客服',
      orders: '我的订单',
      refunds: '退换退款',
      knowledge: '帮助中心',
      metrics: '服务状态',
      escalations: '人工服务单',
    },
    brand: '智能客服中心',
    brandSub: '订单、物流、售后服务',
    landingBrand: '智能客服中心',
    landingSub: '第五组演示项目',
    landingEyebrow: '一站式自助客服',
    landingTitle: '让售后服务更清楚、更快速',
    landingCopy: '查询订单、追踪物流、申请退款、查看帮助规则，并在需要时转人工协助。',
    landingCta: '进入服务中心',
    landingNote: '演示账号模式，无需登录即可体验。',
    landingStats: ['订单查询', '物流追踪', '人工协助'],
    previewTitle: '服务进度',
    previewSteps: [
      ['订单状态', '可查询'],
      ['物流更新', '实时查看'],
      ['退款申请', '可提交'],
      ['人工服务', '可升级'],
    ],
    refresh: '刷新',
    search: '查询',
    send: '发送',
    resolve: '标记已处理',
    backLanding: '返回首页',
    language: '界面语言',
    chinese: '中文',
    english: '英文',
    accountName: '演示用户',
    accountRole: '客户',
    menuTip: '客户服务模式',
    newSession: '新的会话',
    pages: {
      homeTitle: '用户服务首页',
      homeSub: '查看近期订单、退款进度和人工服务单。',
      chatTitle: '在线客服',
      chatSub: '你可以查询订单、追踪物流、申请退款或提交投诉。',
      ordersTitle: '我的订单',
      ordersSub: '查询订单详情和物流状态。',
      refundsTitle: '退换退款',
      refundsSub: '查看退款申请和处理进度。',
      knowledgeTitle: '帮助中心',
      knowledgeSub: '常见退款、物流和售后问题。',
      metricsTitle: '服务状态',
      metricsSub: '查看当前服务处理情况和安全保护状态。',
      ticketsTitle: '人工服务单',
      ticketsSub: '需要人工协助的服务请求会显示在这里。',
    },
    cards: {
      orders: '订单总数',
      messages: '服务消息',
      refunds: '退款申请',
      openRefunds: '待处理退款',
      tickets: '人工服务单',
      openTickets: '处理中服务单',
      protection: '安全保护',
      protectionNote: '已开启',
      recentOrders: '最近订单',
      recentService: '最近服务记录',
      recentTickets: '待处理服务单',
      serviceQuality: '服务保护',
      refundProgress: '退款进度',
      helpRules: '常见问题',
      helpCases: '服务案例',
    },
    notes: {
      orderRecords: '订单记录',
      customerMessages: '客户沟通记录',
      activeQueue: '等待人工协助',
      refundQueue: '等待处理',
      privacy: '敏感信息保护',
      unsafe: '风险请求拦截',
      review: '人工复核提醒',
      response: '回复安全检查',
    },
    labels: {
      status: '状态',
      orderLookup: '订单查询',
      all: '全部',
      payment: '支付状态',
      amount: '金额',
      customer: '客户',
      shipment: '物流',
      noShipment: '暂无物流',
      noItem: '暂无商品',
      createdAt: '创建时间',
      refund: '退款',
      order: '订单',
      priority: '优先级',
      session: '服务单',
      serviceType: '服务类型',
      completed: '已完成',
      noOrders: '暂无订单。',
      noRefunds: '暂无退款记录，可通过在线客服创建。',
      noTickets: '暂无人工服务单。',
      loading: '正在加载数据...',
      unable: '数据加载失败，请稍后重试。',
      notFound: '未找到订单。',
      emptyChatTitle: '开始一次服务对话',
      emptyChatCopy: '可以先查询订单，再继续追问物流或申请售后。',
      processing: '正在处理...',
      failed: '请求失败，请确认后端服务已启动后再试。',
    },
    prompts: [
      '我想查订单202404250001',
      '那物流到哪里了？',
      '7天无理由退款规则是什么？',
      '订单202404250002 我要退款，质量有问题',
      '我要投诉，你们服务太差了，我要找经理',
    ],
  },
  en: {
    nav: {
      home: 'Home',
      chat: 'Live Chat',
      orders: 'My Orders',
      refunds: 'Returns & Refunds',
      knowledge: 'Help Center',
      metrics: 'Service Status',
      escalations: 'Support Tickets',
    },
    brand: 'Smart Service',
    brandSub: 'Orders, delivery, returns',
    landingBrand: 'Smart Service Center',
    landingSub: 'CA6123 Group 5',
    landingEyebrow: 'Self-service support',
    landingTitle: 'Clearer and faster customer support',
    landingCopy: 'Check orders, track deliveries, request refunds, browse help topics, and ask for staff assistance when needed.',
    landingCta: 'Open service center',
    landingNote: 'Demo account mode. No sign-in required.',
    landingStats: ['Order help', 'Delivery tracking', 'Staff support'],
    previewTitle: 'Service progress',
    previewSteps: [
      ['Order status', 'Available'],
      ['Delivery updates', 'Live'],
      ['Refund request', 'Ready'],
      ['Staff support', 'Available'],
    ],
    refresh: 'Refresh',
    search: 'Search',
    send: 'Send',
    resolve: 'Mark resolved',
    backLanding: 'Back to landing',
    language: 'Language',
    chinese: 'Chinese',
    english: 'English',
    accountName: 'Demo Customer',
    accountRole: 'Customer',
    menuTip: 'Customer service mode',
    newSession: 'New conversation',
    pages: {
      homeTitle: 'Service Home',
      homeSub: 'Review recent orders, refund progress, and support tickets.',
      chatTitle: 'Live Chat',
      chatSub: 'Ask about orders, delivery, refunds, or complaints.',
      ordersTitle: 'My Orders',
      ordersSub: 'Search order details and delivery status.',
      refundsTitle: 'Returns & Refunds',
      refundsSub: 'Review refund requests and handling progress.',
      knowledgeTitle: 'Help Center',
      knowledgeSub: 'Common questions about refunds, delivery, and after-sales service.',
      metricsTitle: 'Service Status',
      metricsSub: 'A simple overview of service handling and protection status.',
      ticketsTitle: 'Support Tickets',
      ticketsSub: 'Requests that need staff assistance appear here.',
    },
    cards: {
      orders: 'Total orders',
      messages: 'Service messages',
      refunds: 'Refund requests',
      openRefunds: 'Pending refunds',
      tickets: 'Support tickets',
      openTickets: 'Open tickets',
      protection: 'Protection',
      protectionNote: 'Enabled',
      recentOrders: 'Recent Orders',
      recentService: 'Recent Service',
      recentTickets: 'Open Support Tickets',
      serviceQuality: 'Service Protection',
      refundProgress: 'Refund Progress',
      helpRules: 'Common Questions',
      helpCases: 'Service Examples',
    },
    notes: {
      orderRecords: 'order records',
      customerMessages: 'customer conversations',
      activeQueue: 'waiting for staff support',
      refundQueue: 'waiting for review',
      privacy: 'Sensitive information protection',
      unsafe: 'Unsafe request blocking',
      review: 'Staff review reminders',
      response: 'Reply safety check',
    },
    labels: {
      status: 'Status',
      orderLookup: 'Order lookup',
      all: 'All',
      payment: 'Payment',
      amount: 'Amount',
      customer: 'Customer',
      shipment: 'Delivery',
      noShipment: 'No delivery record',
      noItem: 'No item',
      createdAt: 'Created',
      refund: 'Refund',
      order: 'Order',
      priority: 'Priority',
      session: 'Ticket',
      serviceType: 'Service type',
      completed: 'Completed',
      noOrders: 'No orders yet.',
      noRefunds: 'No refund records yet. You can create one in Live Chat.',
      noTickets: 'No support tickets.',
      loading: 'Loading data...',
      unable: 'Unable to load data. Please try again later.',
      notFound: 'Order not found.',
      emptyChatTitle: 'Start a service conversation',
      emptyChatCopy: 'Try checking an order first, then ask about delivery or after-sales service.',
      processing: 'Processing...',
      failed: 'Request failed. Please confirm the service is running and try again.',
    },
    prompts: [
      'I want to check order 202404250001',
      'Where is the delivery now?',
      'What is the seven-day return policy?',
      'I want a refund for order 202404250002 because of a quality issue.',
      'I want to file a complaint and speak with a manager.',
    ],
  },
} as const;

function App() {
  const [entered, setEntered] = useState(() => window.localStorage.getItem('agentic-cs-entered') === 'true');
  const [lang, setLang] = useState<Lang>(() => (window.localStorage.getItem('agentic-cs-lang') === 'en' ? 'en' : 'zh'));
  const [tab, setTab] = useState<Tab>('home');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const t = i18n[lang];

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

  function changeLang(next: Lang) {
    window.localStorage.setItem('agentic-cs-lang', next);
    setLang(next);
  }

  if (!entered) {
    return <LandingPage lang={lang} onLangChange={changeLang} onEnter={enterApp} />;
  }

  return (
    <div className="appShell">
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="brand">
          <div className="brandMark"><Bot size={20} /></div>
          <div>
            <strong>{t.brand}</strong>
            <span>{t.brandSub}</span>
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
                <span>{t.nav[item.id]}</span>
              </button>
            );
          })}
        </nav>
        <AccountMenu lang={lang} onLangChange={changeLang} onExit={exitApp} />
      </aside>
      <main className="workspace">
        <div className="mobileTopbar">
          <button className="iconButton" onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
          <strong>{t.nav[tab]}</strong>
        </div>
        <button className={`scrim ${sidebarOpen ? 'show' : ''}`} onClick={() => setSidebarOpen(false)} aria-label="Close navigation" />
        <section className="content">
          {tab === 'home' && <HomeDashboard lang={lang} />}
          {tab === 'chat' && <Chat lang={lang} />}
          {tab === 'orders' && <OrdersAndLogistics lang={lang} />}
          {tab === 'refunds' && <Refunds lang={lang} />}
          {tab === 'knowledge' && <Knowledge lang={lang} />}
          {tab === 'metrics' && <ServiceStatus lang={lang} />}
          {tab === 'escalations' && <Escalations lang={lang} />}
        </section>
      </main>
    </div>
  );
}

function LandingPage({ lang, onLangChange, onEnter }: { lang: Lang; onLangChange: (lang: Lang) => void; onEnter: () => void }) {
  const t = i18n[lang];
  return (
    <main className="landing">
      <div className="landingOverlay" />
      <nav className="landingNav">
        <div className="brand inverse">
          <div className="brandMark"><Bot size={20} /></div>
          <div>
            <strong>{t.landingBrand}</strong>
            <span>{t.landingSub}</span>
          </div>
        </div>
        <div className="heroActions">
          <LanguageButtons lang={lang} onLangChange={onLangChange} />
          <button className="secondaryButton" onClick={onEnter}>{t.landingCta}</button>
        </div>
      </nav>
      <div className="landingGrid">
        <div className="heroCopy">
          <span className="eyebrow"><Sparkles size={16} /> {t.landingEyebrow}</span>
          <h1>{t.landingTitle}</h1>
          <p>{t.landingCopy}</p>
          <div className="heroActions">
            <button className="primaryButton" onClick={onEnter}><MessageSquare size={18} /> {t.landingCta}</button>
            <span>{t.landingNote}</span>
          </div>
          <div className="heroStats">
            {t.landingStats.map(item => <MetricMini key={item} label={item} value="✓" />)}
          </div>
        </div>
        <div className="heroPreview" aria-label="Service preview">
          <div className="previewHeader">
            <span />
            <span />
            <span />
            <strong>{t.previewTitle}</strong>
          </div>
          <div className="previewBody">
            {t.previewSteps.map(([label, value], index) => (
              <PreviewStep key={label} label={label} value={value} tone={index === 3 ? 'warning' : index === 0 ? 'success' : 'info'} />
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}

function HomeDashboard({ lang }: { lang: Lang }) {
  const t = i18n[lang];
  const { data, loading, error, refresh } = useApiData<any>('/api/admin/dashboard', lang);
  const metrics = data?.metrics || {};

  return (
    <div className="page">
      <PageHeader
        icon={Home}
        title={t.pages.homeTitle}
        subtitle={t.pages.homeSub}
        action={<button onClick={refresh}><RefreshCcw size={16} /> {t.refresh}</button>}
      />
      {loading && <LoadingState lang={lang} />}
      {error && <ErrorState message={error} />}
      {data && (
        <>
          <div className="metricGrid">
            <MetricCard label={t.cards.orders} value={metrics.total_orders ?? data.recent_orders?.length ?? 0} note={t.notes.orderRecords} />
            <MetricCard label={t.cards.refunds} value={metrics.total_refunds ?? 0} note={t.cards.openRefunds} />
            <MetricCard label={t.cards.tickets} value={metrics.open_escalations ?? 0} note={t.notes.activeQueue} tone="warning" />
            <MetricCard label={t.cards.protection} value={lang === 'zh' ? '开启' : 'On'} note={t.cards.protectionNote} tone="success" />
          </div>

          <div className="threeColumn">
            <Panel title={t.cards.recentOrders} icon={PackageSearch}>
              <CompactList
                items={data.recent_orders}
                empty={t.labels.noOrders}
                render={(item: any) => (
                  <>
                    <strong>{item.order_id}</strong>
                    <span>{displayStatus(item.status, lang)} · {formatMoney(item.total_amount, lang)}</span>
                  </>
                )}
              />
            </Panel>
            <Panel title={t.cards.recentService} icon={MessageSquare}>
              <CompactList
                items={data.recent_sessions}
                empty={lang === 'zh' ? '暂无服务记录。' : 'No service history yet.'}
                render={(item: any) => (
                  <>
                    <strong>{serviceType(item.last_intent, lang)}</strong>
                    <span>{item.message_count} {lang === 'zh' ? '条消息' : 'messages'}</span>
                  </>
                )}
              />
            </Panel>
            <Panel title={t.cards.recentTickets} icon={AlertTriangle}>
              <CompactList
                items={data.open_escalations}
                empty={t.labels.noTickets}
                render={(item: any) => (
                  <>
                    <strong>{displayPriority(item.emotion_level, lang)}</strong>
                    <span>{displayDemoText(item.escalation_reason || item.content, lang)}</span>
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

function Chat({ lang }: { lang: Lang }) {
  const t = i18n[lang];
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [input, setInput] = useState<string>(t.prompts[0]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setInput(i18n[lang].prompts[0]);
  }, [lang]);

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
        intent: res.data.intent,
        safety_report: res.data.safety_report,
      }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: t.labels.failed, intent: 'error' }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page fullHeight">
      <PageHeader icon={MessageSquare} title={t.pages.chatTitle} subtitle={t.pages.chatSub} badge={sessionId ? t.labels.completed : t.newSession} />
      <div className="chatLayout">
        <div className="chatSurface">
          <div className="messageStream">
            {messages.length === 0 && (
              <div className="emptyChat">
                <Bot size={34} />
                <strong>{t.labels.emptyChatTitle}</strong>
                <span>{t.labels.emptyChatCopy}</span>
              </div>
            )}
            {messages.map((message, index) => <ChatBubble key={`${message.role}-${index}`} message={message} lang={lang} />)}
            {loading && <div className="message assistant">{t.labels.processing}</div>}
          </div>
          <div className="promptRow">
            {t.prompts.map(prompt => (
              <button className="promptChip" key={prompt} onClick={() => send(prompt)}>{prompt}</button>
            ))}
          </div>
          <div className="composer">
            <input
              value={input}
              onChange={event => setInput(event.target.value)}
              onKeyDown={event => event.key === 'Enter' && send()}
              placeholder={lang === 'zh' ? '输入订单、物流、退款或投诉问题...' : 'Ask about orders, delivery, refunds, or complaints...'}
            />
            <button onClick={() => send()} disabled={loading || !input.trim()}><Send size={18} /> {t.send}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function OrdersAndLogistics({ lang }: { lang: Lang }) {
  const t = i18n[lang];
  const [status, setStatus] = useState('all');
  const [orderId, setOrderId] = useState('202404250001');
  const [lookup, setLookup] = useState<any>(null);
  const [lookupError, setLookupError] = useState('');
  const path = `/api/admin/orders?limit=50${status === 'all' ? '' : `&status=${encodeURIComponent(status)}`}`;
  const { data, loading, error, refresh } = useApiData<any[]>(path, lang);

  async function loadOrder() {
    setLookupError('');
    try {
      const res = await client.get(`/api/orders/${orderId}`);
      setLookup(res.data);
    } catch {
      setLookup(null);
      setLookupError(t.labels.notFound);
    }
  }

  return (
    <div className="page">
      <PageHeader
        icon={Truck}
        title={t.pages.ordersTitle}
        subtitle={t.pages.ordersSub}
        action={<button onClick={refresh}><RefreshCcw size={16} /> {t.refresh}</button>}
      />
      <div className="toolBand">
        <label>
          {t.labels.status}
          <select value={status} onChange={event => setStatus(event.target.value)}>
            <option value="all">{t.labels.all}</option>
            {['pending_ship', 'shipped', 'signed', 'completed', 'cancelled'].map(item => (
              <option key={item} value={item}>{displayStatus(item, lang)}</option>
            ))}
          </select>
        </label>
        <label className="lookupField">
          {t.labels.orderLookup}
          <span>
            <input value={orderId} onChange={event => setOrderId(event.target.value)} />
            <button onClick={loadOrder}><Search size={16} /> {t.search}</button>
          </span>
        </label>
      </div>
      {lookupError && <ErrorState message={lookupError} />}
      {lookup && (
        <Panel title={`${t.labels.order} ${lookup.order_id}`} icon={PackageSearch}>
          <div className="detailGrid">
            <Detail label={t.labels.status} value={displayStatus(lookup.status, lang)} />
            <Detail label={t.labels.payment} value={displayStatus(lookup.payment_status, lang)} />
            <Detail label={t.labels.amount} value={formatMoney(lookup.total_amount, lang)} />
            <Detail label={t.labels.customer} value={displayCustomer(lookup.customer?.name, lang)} />
          </div>
        </Panel>
      )}
      {loading && <LoadingState lang={lang} />}
      {error && <ErrorState message={error} />}
      <div className="dataList">
        {(data || []).map(order => (
          <div className="dataRow" key={order.order_id}>
            <div>
              <strong>{order.order_id}</strong>
              <span>{displayProduct(order.items?.[0]?.product_name || t.labels.noItem, lang)} · {displayCustomer(order.customer?.name, lang)}</span>
            </div>
            <div>
              <span>{order.shipment?.carrier_name ? displayCarrier(order.shipment.carrier_name, lang) : t.labels.noShipment}</span>
              <small>{order.shipment?.tracking_number || 'n/a'}</small>
            </div>
            <strong>{formatMoney(order.total_amount, lang)}</strong>
            <StatusPill tone={orderTone(order.status)} label={displayStatus(order.status, lang)} />
          </div>
        ))}
        {!loading && data?.length === 0 && <EmptyState text={t.labels.noOrders} />}
      </div>
    </div>
  );
}

function Refunds({ lang }: { lang: Lang }) {
  const t = i18n[lang];
  const [status, setStatus] = useState('all');
  const path = `/api/admin/refunds?limit=50${status === 'all' ? '' : `&status=${encodeURIComponent(status)}`}`;
  const { data, loading, error, refresh } = useApiData<any[]>(path, lang);

  return (
    <div className="page">
      <PageHeader
        icon={RotateCcw}
        title={t.pages.refundsTitle}
        subtitle={t.pages.refundsSub}
        action={<button onClick={refresh}><RefreshCcw size={16} /> {t.refresh}</button>}
      />
      <div className="toolBand">
        <label>
          {t.labels.status}
          <select value={status} onChange={event => setStatus(event.target.value)}>
            <option value="all">{t.labels.all}</option>
            {['pending', 'approved', 'rejected', 'completed'].map(item => (
              <option key={item} value={item}>{displayStatus(item, lang)}</option>
            ))}
          </select>
        </label>
      </div>
      {loading && <LoadingState lang={lang} />}
      {error && <ErrorState message={error} />}
      <div className="dataList">
        {(data || []).map(refund => (
          <div className="dataRow" key={refund.id}>
            <div>
              <strong>{t.labels.refund} #{refund.id}</strong>
              <span>{displayReason(refund.reason, lang)} · {refund.order?.order_id || 'n/a'}</span>
            </div>
            <div>
              <span>{displayCustomer(refund.order?.customer?.name, lang)}</span>
              <small>{formatDate(refund.created_at, lang)}</small>
            </div>
            <strong>{formatMoney(refund.amount, lang)}</strong>
            <StatusPill tone={refund.status === 'pending' ? 'warning' : 'success'} label={displayStatus(refund.status, lang)} />
          </div>
        ))}
        {!loading && data?.length === 0 && <EmptyState text={t.labels.noRefunds} />}
      </div>
    </div>
  );
}

function Knowledge({ lang }: { lang: Lang }) {
  const t = i18n[lang];
  const { data, loading, error, refresh } = useApiData<any>('/api/admin/shared-knowledge', lang);
  return (
    <div className="page">
      <PageHeader
        icon={BookOpen}
        title={t.pages.knowledgeTitle}
        subtitle={t.pages.knowledgeSub}
        action={<button onClick={refresh}><RefreshCcw size={16} /> {t.refresh}</button>}
      />
      {loading && <LoadingState lang={lang} />}
      {error && <ErrorState message={error} />}
      {data && (
        <div className="knowledgeGrid">
          <Panel title={t.cards.helpRules} icon={ShieldCheck}>
            <div className="stack">
              {data.policy_rules.map((rule: any) => (
                <div className="knowledgeItem" key={rule.rule_id}>
                  <strong>{displayHelpTitle(rule.title, lang)}</strong>
                  <span>{helpDecision(rule.decision, lang)}</span>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title={t.cards.helpCases} icon={BookOpen}>
            <div className="stack">
              {data.historical_cases.map((item: any) => (
                <div className="knowledgeItem" key={item.case_id}>
                  <strong>{displayHelpTitle(item.title, lang)}</strong>
                  <span>{displayStatus(item.outcome, lang)}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}

function ServiceStatus({ lang }: { lang: Lang }) {
  const t = i18n[lang];
  const { data: metrics, loading: metricsLoading, error: metricsError, refresh: refreshMetrics } = useApiData<any>('/api/admin/metrics', lang);
  const { data: safety, loading: safetyLoading, error: safetyError, refresh: refreshSafety } = useApiData<any>('/api/admin/evaluation/safety', lang);

  return (
    <div className="page">
      <PageHeader
        icon={BarChart3}
        title={t.pages.metricsTitle}
        subtitle={t.pages.metricsSub}
        action={<button onClick={() => { refreshMetrics(); refreshSafety(); }}><RefreshCcw size={16} /> {t.refresh}</button>}
      />
      {(metricsLoading || safetyLoading) && <LoadingState lang={lang} />}
      {(metricsError || safetyError) && <ErrorState message={metricsError || safetyError || t.labels.unable} />}
      {metrics && (
        <div className="metricGrid">
          <MetricCard label={t.cards.messages} value={metrics.total_messages ?? 0} note={t.notes.customerMessages} />
          <MetricCard label={t.cards.openRefunds} value={metrics.open_refunds ?? 0} note={t.notes.refundQueue} />
          <MetricCard label={t.cards.openTickets} value={metrics.open_escalations ?? 0} note={t.notes.activeQueue} tone="warning" />
          <MetricCard label={t.cards.protection} value={lang === 'zh' ? '正常' : 'Normal'} note={t.cards.protectionNote} tone="success" />
        </div>
      )}
      {safety && (
        <Panel title={t.cards.serviceQuality} icon={ShieldCheck}>
          <div className="safetyGrid">
            {[
              [t.notes.privacy, safety.summary?.pii_redaction_success_rate?.rate],
              [t.notes.unsafe, safety.summary?.input_guardrail_block_rate?.rate],
              [t.notes.review, safety.summary?.hitl_escalation_rule_accuracy?.rate],
              [t.notes.response, safety.summary?.output_guardrail_success_rate?.rate],
            ].map(([label, rate]) => (
              <div className="safetyItem" key={String(label)}>
                <span>{label}</span>
                <strong>{Number(rate || 0)}%</strong>
                <small>{lang === 'zh' ? '服务保护通过' : 'protection check passed'}</small>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function Escalations({ lang }: { lang: Lang }) {
  const t = i18n[lang];
  const { data, loading, error, refresh } = useApiData<any[]>('/api/admin/escalations', lang);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function resolve(id: number) {
    setBusyId(id);
    try {
      await client.post(`/api/admin/escalations/${id}/resolve`, { note: 'resolved from customer UI' });
      refresh();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page">
      <PageHeader
        icon={AlertTriangle}
        title={t.pages.ticketsTitle}
        subtitle={t.pages.ticketsSub}
        action={<button onClick={refresh}><RefreshCcw size={16} /> {t.refresh}</button>}
      />
      {loading && <LoadingState lang={lang} />}
      {error && <ErrorState message={error} />}
      <div className="dataList">
        {(data || []).map(item => (
          <div className="dataRow escalationRow" key={item.id}>
            <div>
              <strong>{displayPriority(item.emotion_level, lang)} · {t.labels.session} {displaySession(item.session_id, lang)}</strong>
              <span>{displayDemoText(item.content, lang)}</span>
              <small>{displayDemoText(item.escalation_reason || '', lang)}</small>
            </div>
            <StatusPill tone="warning" label={displayStatus(item.status, lang)} />
            <button onClick={() => resolve(item.id)} disabled={busyId === item.id}>
              <CheckCircle2 size={16} /> {t.resolve}
            </button>
          </div>
        ))}
        {!loading && data?.length === 0 && <EmptyState text={t.labels.noTickets} />}
      </div>
    </div>
  );
}

function AccountMenu({ lang, onLangChange, onExit }: { lang: Lang; onLangChange: (lang: Lang) => void; onExit: () => void }) {
  const [open, setOpen] = useState(false);
  const t = i18n[lang];
  return (
    <div className="accountBox">
      {open && (
        <div className="accountMenu">
          <div className="accountMenuLabel"><Languages size={16} /> {t.language}</div>
          <LanguageButtons lang={lang} onLangChange={onLangChange} />
          <button disabled><ShieldCheck size={16} /> {t.menuTip}</button>
          <button onClick={onExit}><LogOut size={16} /> {t.backLanding}</button>
        </div>
      )}
      <button className="accountButton" onClick={() => setOpen(value => !value)}>
        <span className="avatar"><UserRound size={18} /></span>
        <span>
          <strong>{t.accountName}</strong>
          <small>{t.accountRole}</small>
        </span>
        <ChevronDown size={16} />
      </button>
    </div>
  );
}

function LanguageButtons({ lang, onLangChange }: { lang: Lang; onLangChange: (lang: Lang) => void }) {
  const t = i18n[lang];
  return (
    <div className="languageSwitch">
      <button className={lang === 'zh' ? 'active' : ''} onClick={() => onLangChange('zh')}>{t.chinese}</button>
      <button className={lang === 'en' ? 'active' : ''} onClick={() => onLangChange('en')}>{t.english}</button>
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

function ChatBubble({ message, lang }: { message: ChatMessage; lang: Lang }) {
  return (
    <div className={`message ${message.role}`}>
      <p>{message.role === 'assistant' ? displayAssistantReply(message, lang) : displayDemoText(message.content, lang)}</p>
    </div>
  );
}

function StatusPill({ tone, label }: { tone: Tone; label: string }) {
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

function LoadingState({ lang }: { lang: Lang }) {
  return <div className="stateLine">{i18n[lang].labels.loading}</div>;
}

function ErrorState({ message }: { message: string }) {
  return <div className="stateLine errorState">{message}</div>;
}

function EmptyState({ text }: { text: string }) {
  return <div className="emptyState">{text}</div>;
}

function useApiData<T>(path: string, lang: Lang) {
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
        if (alive) setError(i18n[lang].labels.unable);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [path, tick, lang]);

  return useMemo(() => ({
    data,
    loading,
    error,
    refresh: () => setTick(value => value + 1),
  }), [data, loading, error]);
}

function displayAssistantReply(message: ChatMessage, lang: Lang) {
  if (lang === 'zh') return message.content;
  if (message.safety_report?.input?.blocked) {
    return 'This request cannot be processed because it asks for restricted instructions or sensitive information. Please describe a real service issue instead.';
  }
  if (message.intent === 'order') return 'Here are the order details we found, including order status, payment status, delivery record, and total amount.';
  if (message.intent === 'logistics') return 'Here is the latest delivery information for your order. If the parcel is delayed or marked delivered but not received, staff support can help review it.';
  if (message.intent === 'refund') {
    if (message.content.includes('申请') || message.content.toLowerCase().includes('refund')) {
      return 'Your refund request has been submitted. It will be reviewed within 1-3 business days. Approved refunds usually return to the original payment method within 3-7 business days.';
    }
    return 'For seller-responsibility issues such as quality problems, damaged items, wrong items, or items not matching the description, a refund or exchange can be requested. Seven-day returns require the item to remain resellable.';
  }
  if (message.intent === 'complaint') return 'Your support ticket has been created and staff support will review it with priority. Please keep your contact channel available.';
  if (message.intent === 'unknown') return 'I need a little more information. Please provide an order number, tracking number, or describe whether you need order, delivery, refund, or complaint support.';
  return displayDemoText(message.content, lang);
}

function displayDemoText(value: string | undefined, lang: Lang) {
  if (!value) return '';
  if (lang === 'zh') return value;
  let text = value;
  const replacements: Array<[RegExp, string]> = [
    [/我要投诉，你们服务太差了，我要找经理/g, 'I want to file a complaint. Your service is poor and I want to speak with a manager.'],
    [/商品质量有问题/g, 'The item has a quality issue.'],
    [/物流太慢了/g, 'The delivery is too slow.'],
    [/我要投诉服务态度/g, 'I want to complain about the service attitude.'],
    [/服务太差/g, 'poor service'],
    [/情绪强烈/g, 'strong negative emotion'],
    [/涉及投诉\/曝光\/法律风险/g, 'complaint or legal-risk keywords detected'],
    [/用户明确要求人工/g, 'customer requested staff support'],
    [/演示数据/g, 'demo data'],
    [/质量有问题/g, 'quality issue'],
    [/订单/g, 'order'],
    [/退款/g, 'refund'],
    [/物流/g, 'delivery'],
    [/投诉/g, 'complaint'],
  ];
  for (const [pattern, replacement] of replacements) text = text.replace(pattern, replacement);
  return text;
}

function displayStatus(value: string | undefined, lang: Lang) {
  const zh: Record<string, string> = {
    pending_ship: '待发货',
    pending: '处理中',
    shipped: '运输中',
    signed: '已签收',
    completed: '已完成',
    cancelled: '已取消',
    paid: '已支付',
    refunded: '已退款',
    approved: '已通过',
    rejected: '未通过',
    open: '处理中',
    resolved: '已处理',
    handled: '已处理',
    resolved_demo: '已处理',
  };
  const en: Record<string, string> = {
    pending_ship: 'Preparing',
    pending: 'Pending',
    shipped: 'In transit',
    signed: 'Delivered',
    completed: 'Completed',
    cancelled: 'Cancelled',
    paid: 'Paid',
    refunded: 'Refunded',
    approved: 'Approved',
    rejected: 'Rejected',
    open: 'Open',
    resolved: 'Resolved',
    handled: 'Handled',
    resolved_demo: 'Resolved',
  };
  const map = lang === 'zh' ? zh : en;
  return map[value || ''] || value || 'n/a';
}

function displayPriority(value: string | undefined, lang: Lang) {
  const zh: Record<string, string> = { high: '高优先级', medium: '中优先级', low: '普通优先级' };
  const en: Record<string, string> = { high: 'High priority', medium: 'Medium priority', low: 'Normal priority' };
  return (lang === 'zh' ? zh : en)[value || ''] || (lang === 'zh' ? '普通优先级' : 'Normal priority');
}

function displayReason(value: string | undefined, lang: Lang) {
  const zh: Record<string, string> = {
    quality_issue: '质量问题',
    seven_day: '七天无理由',
    not_as_described: '描述不符',
    wrong_item: '错发/少发',
    damaged: '商品破损',
    other: '协商退款',
  };
  const en: Record<string, string> = {
    quality_issue: 'Quality issue',
    seven_day: 'Seven-day return',
    not_as_described: 'Not as described',
    wrong_item: 'Wrong or missing item',
    damaged: 'Damaged item',
    other: 'Other refund request',
  };
  return (lang === 'zh' ? zh : en)[value || ''] || value || 'n/a';
}

function serviceType(value: string | undefined, lang: Lang) {
  const zh: Record<string, string> = { order: '订单服务', logistics: '物流服务', refund: '退款服务', complaint: '投诉服务', unknown: '客户服务' };
  const en: Record<string, string> = { order: 'Order support', logistics: 'Delivery support', refund: 'Refund support', complaint: 'Complaint support', unknown: 'Customer support' };
  return (lang === 'zh' ? zh : en)[value || 'unknown'] || (lang === 'zh' ? '客户服务' : 'Customer support');
}

function displayProduct(value: string, lang: Lang) {
  if (lang === 'zh') return value;
  return value.replace('智能手表', 'Smart Watch');
}

function displayCustomer(value: string | undefined, lang: Lang) {
  if (!value) return lang === 'zh' ? '客户' : 'Customer';
  if (lang === 'zh') return value;
  return value.replace(/^用户(\d+)/, 'Customer $1');
}

function displayCarrier(value: string, lang: Lang) {
  if (lang === 'zh') return value;
  const map: Record<string, string> = {
    顺丰速运: 'SF Express',
    京东物流: 'JD Logistics',
    圆通速递: 'YTO Express',
    中通快递: 'ZTO Express',
  };
  return map[value] || value;
}

function displayHelpTitle(value: string, lang: Lang) {
  if (lang === 'zh') return value;
  const map: Record<string, string> = {
    卖家责任退款规则: 'Seller-responsibility refund rule',
    电子产品七天无理由规则: 'Seven-day return rule for electronics',
    '虚拟/定制商品无理由退款限制': 'Return limits for virtual or customized products',
    'VIP/Gold 协商退款人工复核': 'Staff review for VIP or Gold refund requests',
    'VIP 高价值电子产品七天退货': 'VIP high-value electronics return',
    签收未收到丢件争议: 'Delivered but not received case',
    重复投诉升级处理: 'Repeated complaint escalation',
  };
  return map[value] || displayDemoText(value, lang);
}

function helpDecision(value: string | undefined, lang: Lang) {
  const zh: Record<string, string> = { approve: '符合条件时可支持', deny: '部分场景不支持', escalate: '需要人工复核' };
  const en: Record<string, string> = { approve: 'Supported when conditions are met', deny: 'Not supported in some cases', escalate: 'Staff review required' };
  return (lang === 'zh' ? zh : en)[value || ''] || (lang === 'zh' ? '可咨询客服' : 'Contact support for details');
}

function displaySession(value: string | undefined, lang: Lang) {
  if (!value) return 'n/a';
  let normalized = value
    .replace(/^deepseek-/, '')
    .replace(/^acceptance-/, '')
    .replace(/^debug-/, '')
    .replace(/^seed-/, '')
    .replace(/^complaint/, lang === 'zh' ? '客诉' : 'complaint')
    .replace(/^service/, lang === 'zh' ? '服务' : 'service');
  normalized = normalized.replace(/[^\p{L}\p{N}-]/gu, '-');
  return lang === 'zh' ? `服务单-${normalized}` : `ticket-${normalized}`;
}

function orderTone(status: string): Tone {
  if (status === 'completed' || status === 'signed') return 'success';
  if (status === 'shipped') return 'info';
  if (status === 'pending_ship') return 'warning';
  return 'neutral';
}

function formatMoney(value: number | string | null | undefined, lang: Lang) {
  const numeric = Number(value || 0);
  return lang === 'zh' ? `¥${numeric.toFixed(2)}` : `S$${numeric.toFixed(2)}`;
}

function formatDate(value: string | null | undefined, lang: Lang) {
  if (!value) return 'n/a';
  return new Date(value).toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-SG', { hour12: false });
}

function createRootApp() {
  createRoot(document.getElementById('root')!).render(<App />);
}

createRootApp();

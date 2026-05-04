import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import axios from 'axios';
import { AlertTriangle, BarChart3, Bot, CheckCircle2, MessageSquare, PackageSearch, Send } from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

type ChatMessage = { role: 'user' | 'assistant'; content: string; agent?: string; intent?: string; rag_sources?: string[] };

function App() {
  const [tab, setTab] = useState('chat');
  return (
    <div className="app">
      <aside>
        <h1>Agentic CS</h1>
        <button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}><MessageSquare size={18}/> Chat</button>
        <button className={tab === 'orders' ? 'active' : ''} onClick={() => setTab('orders')}><PackageSearch size={18}/> Orders</button>
        <button className={tab === 'metrics' ? 'active' : ''} onClick={() => setTab('metrics')}><BarChart3 size={18}/> Metrics</button>
        <button className={tab === 'escalations' ? 'active' : ''} onClick={() => setTab('escalations')}><AlertTriangle size={18}/> Escalations</button>
      </aside>
      <main>
        {tab === 'chat' && <Chat />}
        {tab === 'orders' && <Orders />}
        {tab === 'metrics' && <Metrics />}
        {tab === 'escalations' && <Escalations />}
      </main>
    </div>
  );
}

function Chat() {
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [input, setInput] = useState('我想查订单202404250001');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  async function send() {
    if (!input.trim()) return;
    const userMsg: ChatMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    const res = await axios.post(`${API}/api/chat`, { session_id: sessionId, message: input });
    setSessionId(res.data.session_id);
    setMessages(prev => [...prev, { role: 'assistant', content: res.data.response, agent: res.data.agent, intent: res.data.intent, rag_sources: res.data.rag_sources }]);
    setInput('');
    setLoading(false);
  }

  return <section>
    <header><Bot size={22}/><h2>客服对话</h2><span>{sessionId || 'new session'}</span></header>
    <div className="chat">
      {messages.map((m, i) => <div key={i} className={`msg ${m.role}`}>
        <div>{m.content}</div>
        {m.role === 'assistant' && <small>Agent: {m.agent} | Intent: {m.intent} | RAG: {(m.rag_sources || []).join(', ') || 'none'}</small>}
      </div>)}
      {loading && <div className="msg assistant">处理中...</div>}
    </div>
    <div className="composer">
      <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} />
      <button onClick={send}><Send size={18}/>发送</button>
    </div>
  </section>;
}

function Orders() {
  const [orderId, setOrderId] = useState('202404250001');
  const [order, setOrder] = useState<any>(null);
  const [error, setError] = useState('');
  async function load() {
    setError('');
    try {
      const res = await axios.get(`${API}/api/orders/${orderId}`);
      setOrder(res.data);
    } catch {
      setOrder(null);
      setError('未找到订单');
    }
  }
  return <section>
    <header><PackageSearch size={22}/><h2>订单查询</h2></header>
    <div className="toolbar"><input value={orderId} onChange={e => setOrderId(e.target.value)} /><button onClick={load}>查询</button></div>
    {error && <p className="error">{error}</p>}
    {order && <div className="panel">
      <h3>{order.order_id} <span>{order.status}</span></h3>
      <p>金额：¥{order.total_amount}</p>
      <p>客户：{order.customer?.name} / {order.customer?.member_level}</p>
      <h4>商品</h4>{order.items.map((i: any) => <p key={i.sku}>{i.product_name} x{i.quantity}</p>)}
      <h4>物流</h4>{order.shipment?.events.map((e: any) => <p key={e.time}>{e.time} {e.status} {e.detail}</p>)}
    </div>}
  </section>;
}

function Metrics() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { axios.get(`${API}/api/admin/metrics`).then(r => setData(r.data)); }, []);
  return <section>
    <header><BarChart3 size={22}/><h2>指标</h2></header>
    {data && <div className="grid">
      <Metric label="Messages" value={data.total_messages}/>
      <Metric label="Sessions" value={data.total_sessions}/>
      <Metric label="Escalations" value={data.open_escalations}/>
      <Metric label="RAG Hit" value={`${data.rag_hit_rate}%`}/>
    </div>}
    <pre>{JSON.stringify(data, null, 2)}</pre>
  </section>;
}

function Metric({label, value}: {label: string; value: any}) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function Escalations() {
  const [items, setItems] = useState<any[]>([]);
  async function load() { setItems((await axios.get(`${API}/api/admin/escalations`)).data); }
  async function resolve(id: number) { await axios.post(`${API}/api/admin/escalations/${id}/resolve`, { note: 'done' }); load(); }
  useEffect(() => { load(); }, []);
  return <section>
    <header><AlertTriangle size={22}/><h2>人工升级队列</h2></header>
    {items.map(item => <div className="panel row" key={item.id}>
      <div><strong>{item.emotion_level}</strong><p>{item.content}</p><small>{item.escalation_reason}</small></div>
      <button onClick={() => resolve(item.id)}><CheckCircle2 size={18}/>处理完成</button>
    </div>)}
  </section>;
}

createRoot(document.getElementById('root')!).render(<App />);

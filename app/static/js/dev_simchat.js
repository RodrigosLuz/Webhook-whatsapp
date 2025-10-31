/* app/static/js/dev_simchat.js */
(() => {
  'use strict';

  // ---------------- State ----------------
  let es = null;                 // EventSource
  let isConnected = false;
  const seenIds = new Set();     // dedupe por ID do banco

  const chat   = document.getElementById('chat');
  const pnidEl = document.getElementById('pnid');
  const phoneEl= document.getElementById('phone');
  const msgEl  = document.getElementById('msg');
  const pill   = document.getElementById('pill');
  const btnConnect = document.getElementById('btnConnect');

  function fmtTime(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'});
    } catch { return ''; }
  }
  function scrollBottom(){ chat.scrollTop = chat.scrollHeight; }

  function bubble(dir, text, ts) {
    const row = document.createElement('div'); row.className='row '+dir;
    const b = document.createElement('div'); b.className='bubble';
    b.textContent = text || '';
    const t = document.createElement('div'); t.className='ts'; t.textContent = fmtTime(ts);
    b.appendChild(t); row.appendChild(b); chat.appendChild(row); scrollBottom();
  }

  function renderMessage(m){
    if (!m || !m.id) return;
    if (seenIds.has(m.id)) return;   // evita duplicatas
    seenIds.add(m.id);

    const dir = m.direction === 'inbound' ? 'in' : 'out';
    const text = m.text || (m.attachments_meta ? JSON.stringify(m.attachments_meta) : '(sem conteúdo)');
    bubble(dir, text, m.created_at);
  }

  // ---------------- Stream (SSE) ----------------
  function connect() {
    if (isConnected) return;
    const pnid  = encodeURIComponent(pnidEl.value.trim());
    const phone = encodeURIComponent(phoneEl.value.trim());
    if (!pnid || !phone) { alert('Informe PNID e telefone.'); return; }

    if (es) { try { es.close(); } catch {} es = null; }

    es = new EventSource(`/dev/stream?pnid=${pnid}&phone=${phone}`);
    es.onopen = () => {
      isConnected = true;
      btnConnect.textContent = 'Desconectar';
      btnConnect.classList.remove('gray'); btnConnect.classList.add('red');
      pill.textContent = 'Conectado'; pill.classList.remove('off');
    };
    es.onerror = () => { disconnect(); };
    es.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data);
        if (Array.isArray(payload)) payload.forEach(renderMessage);
      } catch { /* ignore */ }
    };
  }

  function disconnect() {
    if (es) try { es.close(); } catch {}
    es = null; isConnected = false;
    btnConnect.textContent = 'Conectar';
    btnConnect.classList.remove('red'); btnConnect.classList.add('gray');
    pill.textContent = 'Desconectado'; pill.classList.add('off');
  }

  btnConnect.addEventListener('click', () => isConnected ? disconnect() : connect());

  // ---------------- Histórico ----------------
  async function loadHistory() {
    const pnid = pnidEl.value.trim();
    const phone = phoneEl.value.trim();
    if (!pnid || !phone) { alert('Informe PNID e telefone.'); return; }

    chat.innerHTML = ''; seenIds.clear();

    const res = await fetch(
      `/dev/messages?pnid=${encodeURIComponent(pnid)}&phone=${encodeURIComponent(phone)}&limit=300`,
      { cache:'no-store' }
    );
    const data = await res.json();
    const messages = (data.messages || []).sort((a,b)=> (a.created_at>b.created_at?1:-1));
    messages.forEach(renderMessage);
  }
  document.getElementById('btnHistory').addEventListener('click', loadHistory);

  // ---------------- Limpar ----------------
  document.getElementById('btnClear').addEventListener('click', () => {
    chat.innerHTML = ''; seenIds.clear(); msgEl.focus();
  });

  // ---------------- Enviar ----------------
  async function handleSend() {
    const text = msgEl.value.trim();
    if (!text) return;
    const pnid = pnidEl.value.trim();
    const phone = phoneEl.value.trim();
    if (!pnid || !phone) { alert('Informe PNID e telefone.'); return; }
    msgEl.value = '';

    if (isConnected) {
      // Webhook real: NÃO ecoa localmente; o SSE desenhará do banco
      const payload = {
        entry:[{changes:[{value:{
          messaging_product:'whatsapp',
          messages:[{from: phone, type:'text', text:{body:text}}],
          metadata:{phone_number_id: pnid}
        }}]}]
      };
      try {
        await fetch('/', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      } catch (e) {
        alert('Falha ao enviar para o webhook: '+e);
      }
    } else {
      // Modo simulado: ecoa inbound e pede ações ao /dev/simulate
      bubble('in', text, new Date().toISOString());
      try {
        const res = await fetch('/dev/simulate', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({phone_number_id: pnid, from: phone, text})
        });
        const data = await res.json();
        const actions = data.actions || [];
        let acc = 0;
        actions.forEach((a, idx) => {
          const d = (Number(a.delay) || (idx>0?5:0)) * 1000;
          acc += d;
          setTimeout(()=>{
            if (a.text) bubble('out', a.text, new Date().toISOString());
            else if (a.template) bubble('out', JSON.stringify(a.template), new Date().toISOString());
          }, acc);
        });
      } catch (e) {
        alert('Falha ao simular: '+e);
      }
    }
  }
  document.getElementById('btnSend').addEventListener('click', handleSend);

  // ---------------- Modo simulado (apenas alterna o modo) ----------------
  document.getElementById('btnSimulate').addEventListener('click', () => {
    // apenas garante que está desconectado; envio é sempre pelo botão Enviar
    disconnect();
    msgEl.focus();
  });

  // UX: Enter envia; Shift+Enter quebra linha
  msgEl.addEventListener('keydown', (e)=>{
    if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  });

  // ---------------- Iniciar já conectado ----------------
  window.addEventListener('load', () => {
    if (pnidEl.value.trim() && phoneEl.value.trim()) connect();
    msgEl.focus();
  });
})();

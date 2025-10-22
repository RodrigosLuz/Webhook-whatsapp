// app.js
const express = require('express');
const crypto = require('crypto');
const app = express();

app.use(express.json());

// ==== CONFIG ====
const port = process.env.PORT || 3000;
const verifyToken = process.env.VERIFY_TOKEN;      // painel Meta
const waToken = process.env.WHATSAPP_TOKEN;        // Cloud API
const phoneNumberId = process.env.PHONE_NUMBER_ID; // ex: 879357005252665
const LOG_LEVEL = (process.env.LOG_LEVEL || 'INFO').toUpperCase(); // DEBUG|INFO|WARN|ERROR

// ==== LOGGER MINIMALISTA (JSON) ====
const levels = { DEBUG: 10, INFO: 20, WARN: 30, ERROR: 40 };
const activeLevel = levels[LOG_LEVEL] ?? levels.INFO;

function nowISO() { return new Date().toISOString(); }
function redact(s) {
  if (!s) return s;
  // mascara tokens longos e telefones
  if (typeof s === 'string' && s.length > 20) return s.slice(0, 6) + '…redacted';
  return s;
}
function maskPhone(p) {
  if (!p) return p;
  return String(p).replace(/(\d{2})(\d{2})(\d{5})(\d{2})(\d{2})/, (_, cc, dd, mid, end1, end2) => `${cc}${dd}${mid.replace(/\d/g,'*')}${end1}${end2}`);
}
function safeJSON(obj) {
  try { return JSON.stringify(obj); } catch { return '"<unserializable>"'; }
}
function log(level, msg, extra={}) {
  if (levels[level] < activeLevel) return;
  const base = { ts: nowISO(), level, msg, ...extra };
  // nunca logar token claro
  if (base.waToken) base.waToken = redact(base.waToken);
  process.stdout.write(safeJSON(base) + '\n');
}
const logger = {
  debug: (msg, extra) => log('DEBUG', msg, extra),
  info:  (msg, extra) => log('INFO',  msg, extra),
  warn:  (msg, extra) => log('WARN',  msg, extra),
  error: (msg, extra) => log('ERROR', msg, extra),
};

// ==== MIDDLEWARE request-id + tempo ====
app.use((req, res, next) => {
  const rid = crypto.randomUUID();
  const start = process.hrtime.bigint();
  req.rid = rid;

  logger.info('http.request', { rid, method: req.method, path: req.path, ip: req.ip });

  res.on('finish', () => {
    const durMs = Number(process.hrtime.bigint() - start) / 1e6;
    logger.info('http.response', { rid, status: res.statusCode, duration_ms: Math.round(durMs) });
  });
  next();
});

// ==== HTTP util ====
async function waPost(payload) {
  const url = `https://graph.facebook.com/v22.0/${phoneNumberId}/messages`;
  const started = Date.now();
  const rid = crypto.randomUUID();

  logger.debug('wa.request', {
    rid, url,
    to: maskPhone(payload?.to),
    type: payload?.type,
    // corpo completo só em DEBUG (Render permite filtrar)
    payload: payload
  });

  const resp = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${waToken}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  const text = await resp.text().catch(() => '');

  logger.info('wa.response', {
    rid, status: resp.status, elapsed_ms: Date.now() - started,
    snippet: text.slice(0, 300) + (text.length > 300 ? '…' : '')
  });

  if (!resp.ok) {
    // tenta extrair erro da Graph API
    let detail;
    try { detail = JSON.parse(text); } catch { detail = { raw: text }; }
    logger.error('wa.error', { rid, status: resp.status, detail });
    throw new Error(`WhatsApp API ${resp.status}`);
  }

  try { return JSON.parse(text); } catch { return {}; }
}

// ==== Helpers de envio ====
async function sendText(to, body) {
  const payload = { messaging_product: 'whatsapp', to, type: 'text', text: { body } };
  return waPost(payload);
}
async function sendTemplate(to, template) {
  const payload = { messaging_product: 'whatsapp', to, type: 'template', template };
  return waPost(payload);
}

// ==== VERIFY (GET) ====
app.get('/', (req, res) => {
  const { 'hub.mode': mode, 'hub.challenge': challenge, 'hub.verify_token': token } = req.query;

  logger.info('webhook.verify', {
    mode, ok: mode === 'subscribe' && token === verifyToken
  });

  if (mode === 'subscribe' && token === verifyToken) {
    return res.status(200).send(challenge);
  }
  return res.status(403).end();
});

// ==== RECEBER (POST) ====
app.post('/', async (req, res) => {
  // log resumido + completo apenas em DEBUG
  logger.info('webhook.incoming', {
    has_entry: Array.isArray(req.body?.entry),
    raw_size: Buffer.byteLength(JSON.stringify(req.body) || '')
  });
  logger.debug('webhook.body', { body: req.body });

  try {
    const entry = req.body.entry?.[0];
    const change = entry?.changes?.[0]?.value;

    const messages = change?.messages;
    if (Array.isArray(messages)) {
      for (const msg of messages) {
        const from = msg.from;
        const text = msg.text?.body || '';
        const name = change?.contacts?.[0]?.profile?.name || 'aí';

        logger.info('msg.in', {
          from: maskPhone(from),
          type: msg.type,
          text_preview: text.slice(0, 80)
        });

        let reply = `Olá, ${name}! Recebemos sua mensagem: "${text}"`;
        if (/^menu$/i.test(text)) {
          reply = 'Menu:\n1) Orçamento\n2) Suporte\n3) Falar com humano';
        }

        await sendText(from, reply);

        logger.info('msg.out', {
          to: maskPhone(from),
          kind: 'text',
          text_preview: reply.slice(0, 80)
        });
      }
    }

    const statuses = change?.statuses;
    if (Array.isArray(statuses)) {
      for (const st of statuses) {
        logger.info('delivery.status', {
          status: st.status,
          msg_id: st.id,
          to: maskPhone(st.recipient_id),
          error: st.errors?.[0]?.title || null
        });
      }
    }

    res.sendStatus(200);
  } catch (e) {
    logger.error('webhook.handler_error', { message: e.message, stack: e.stack?.split('\n')[0] });
    // sempre 200 para evitar re-tentativas infinitas
    res.sendStatus(200);
  }
});

// ==== Envio proativo ====
app.post('/send', async (req, res) => {
  try {
    const { to, text, template } = req.body;
    if (!to) {
      logger.warn('send.missing_to', { body: req.body });
      return res.status(400).json({ error: 'Informe "to"' });
    }
    if (!text && !template) {
      logger.warn('send.missing_content', { to: maskPhone(to) });
      return res.status(400).json({ error: 'Informe "text" ou "template"' });
    }

    logger.info('send.request', {
      to: maskPhone(to),
      mode: text ? 'text' : 'template',
      template_name: template?.name
    });

    const result = text ? await sendText(to, text) : await sendTemplate(to, template);

    logger.info('send.success', { to: maskPhone(to) });
    res.json({ ok: true, result });
  } catch (e) {
    logger.error('send.error', { message: e.message });
    res.status(500).json({ error: e.message });
  }
});

// ==== Healthcheck ====
app.get('/health', (_req, res) => {
  res.json({ ok: true });
});

app.listen(port, () => {
  logger.info('server.start', {
    port,
    node: process.version,
    phoneNumberId,
    verifyToken_set: Boolean(verifyToken),
    waToken_set: Boolean(waToken)
  });
});

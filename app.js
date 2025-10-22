// app.js
const express = require('express');
const app = express();

app.use(express.json());

const port = process.env.PORT || 3000;
const verifyToken = process.env.VERIFY_TOKEN; // mesmo valor configurado no painel do Meta
const waToken = process.env.WHATSAPP_TOKEN;  // token de acesso da Cloud API
const phoneNumberId = process.env.PHONE_NUMBER_ID; // ex: 879357005252665

// --- util genérico para POST na Graph API ---
async function waPost(payload) {
  const url = `https://graph.facebook.com/v22.0/${phoneNumberId}/messages`;
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${waToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    console.error('[WA API ERROR]', resp.status, text);
    throw new Error(`WhatsApp API ${resp.status}: ${text}`);
  }
  return resp.json().catch(() => ({}));
}

// --- helpers de envio ---
async function sendText(to, body) {
  const payload = {
    messaging_product: 'whatsapp',
    to,
    type: 'text',
    text: { body }
  };
  return waPost(payload);
}

async function sendTemplate(to, template) {
  // `template` deve vir no formato da Cloud API, ex:
  // { name: 'hello_world', language: { code: 'en_US' }, components: [...] }
  const payload = {
    messaging_product: 'whatsapp',
    to,
    type: 'template',
    template
  };
  return waPost(payload);
}

// --- VERIFY (GET) ---
app.get('/', (req, res) => {
  const { 'hub.mode': mode, 'hub.challenge': challenge, 'hub.verify_token': token } = req.query;
  if (mode === 'subscribe' && token === verifyToken) {
    console.log('WEBHOOK VERIFIED');
    return res.status(200).send(challenge);
  }
  return res.status(403).end();
});

// --- RECEBER (POST) e auto-responder ---
app.post('/', async (req, res) => {
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
  console.log(`\n\nWebhook received ${ts}\n${JSON.stringify(req.body, null, 2)}\n`);

  try {
    const entry = req.body.entry?.[0];
    const change = entry?.changes?.[0]?.value;

    // Mensagens recebidas
    const messages = change?.messages;
    if (Array.isArray(messages)) {
      for (const msg of messages) {
        const from = msg.from;
        const text = msg.text?.body || '';
        const name = change?.contacts?.[0]?.profile?.name || 'aí';

        let reply = `Olá, ${name}! Recebemos sua mensagem: "${text}"`;
        if (/^menu$/i.test(text)) {
          reply = 'Menu:\n1) Orçamento\n2) Suporte\n3) Falar com humano';
        }

        await sendText(from, reply);
      }
    }

    // Status de entrega (log opcional)
    const statuses = change?.statuses;
    if (Array.isArray(statuses)) {
      for (const st of statuses) {
        console.log(`Status ${st.status} para ${st.id} (to=${st.recipient_id})`);
      }
    }

    res.sendStatus(200);
  } catch (e) {
    console.error('Erro no handler do webhook:', e);
    // Sempre retornar 200 para evitar re-tentativas infinitas do Meta
    res.sendStatus(200);
  }
});

// --- Envio proativo ---
// POST /send
// aceita:
// 1) { "to": "55XXXXXXXXXXX", "text": "mensagem" }
// 2) { "to": "55XXXXXXXXXXX", "template": { name, language, components? } }
app.post('/send', async (req, res) => {
  try {
    const { to, text, template } = req.body;
    if (!to) {
      return res.status(400).json({ error: 'Informe "to"' });
    }

    if (!text && !template) {
      return res.status(400).json({ error: 'Informe "text" ou "template"' });
    }

    let result;
    if (text) {
      result = await sendText(to, text);
    } else {
      result = await sendTemplate(to, template);
    }

    res.json({ ok: true, result });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// --- Healthcheck simples ---
app.get('/health', (_req, res) => res.json({ ok: true }));

app.listen(port, () => {
  console.log(`\nListening on port ${port}\n`);
});

// app.js
const express = require('express');
const app = express();

app.use(express.json());

const port = process.env.PORT || 3000;
const verifyToken = process.env.VERIFY_TOKEN;
const waToken = process.env.WHATSAPP_TOKEN;
const phoneNumberId = process.env.PHONE_NUMBER_ID;

// --- helper pra enviar mensagem de texto ---
async function sendText(to, body) {
  const url = `https://graph.facebook.com/v22.0/${phoneNumberId}/messages`;
  const payload = {
    messaging_product: 'whatsapp',
    to,
    type: 'text',
    text: { body }
  };

  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${waToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });

  if (!resp.ok) {
    const err = await resp.text().catch(() => '');
    console.error('Erro ao enviar mensagem:', resp.status, err);
    throw new Error(`WhatsApp API ${resp.status}`);
  }
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

// --- RECEBER (POST) e responder automaticamente ---
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
        const from = msg.from;                      // ex: "55DDDNÚMERO"
        const text = msg.text?.body || '';
        const name = change?.contacts?.[0]?.profile?.name || 'aí';

        // lógica simples de auto-reply
        let reply = `Olá, ${name}! Recebemos sua mensagem: "${text}"`;
        if (/^menu$/i.test(text)) {
          reply = 'Menu:\n1) Orçamento\n2) Suporte\n3) Falar com humano';
        }

        await sendText(from, reply);
      }
    }

    // Status de entrega (opcional pra log)
    const statuses = change?.statuses;
    if (Array.isArray(statuses)) {
      for (const st of statuses) {
        console.log(`Status ${st.status} para ${st.id} (to=${st.recipient_id})`);
      }
    }

    res.sendStatus(200);
  } catch (e) {
    console.error('Erro no handler do webhook:', e);
    res.sendStatus(200); // sempre 200 pro WhatsApp não re-tentar eternamente
  }
});

// --- Envio proativo: POST /send { "to": "55XXXXXXXXXXX", "text": "oi" } ---
app.post('/send', async (req, res) => {
  try {
    const { to, text } = req.body;
    if (!to || !text) return res.status(400).json({ error: 'Informe "to" e "text"' });
    await sendText(to, text);
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(port, () => {
  console.log(`\nListening on port ${port}\n`);
});

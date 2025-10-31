
# R2D2 - Ambiente de Desenvolvimento com Docker

Este projeto usa Flask com Docker para rodar de forma padronizada em qualquer ambiente.

---

## 🚀 Ciclo Completo de Desenvolvimento

### ✅ 1. Subir o ambiente com rebuild

```bash
docker-compose up --build
```

---

### ✅ 2. Parar e remover containers

```bash
docker-compose down
```

---

### ✅ 3. Parar e remover tudo, incluindo volumes (⚠️ cuidado!)

```bash
docker-compose down --volumes
```

---

### 🔄 4. Rodar em segundo plano

```bash
docker-compose up -d
```

---

### 🔍 5. Ver logs

```bash
docker-compose logs -f
```

---

### 🐚 6. Entrar no terminal do container

```bash
docker-compose exec web bash
```

---

### 🧪 7. Executar comandos isolados

```bash
docker-compose run --rm web flask shell
```

---

## 📄 Variáveis de Ambiente

Crie um arquivo `.env` com:

```env
FLASK_ENV=dev
SECRET_KEY=su4ch4v3
```

E no `docker-compose.yml`:

```yaml
env_file:
  - .env
```

---

## 📌 Observações

- O modo `dev` ativa o debug automático.
- Use `main` ou `hom` no `FLASK_ENV` para simular produção ou homologação.
- As imagens e volumes são persistentes, mesmo após `down`.

---

Desenvolvido por COREGEST/PRU1 - AGU

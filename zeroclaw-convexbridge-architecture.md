# 🦀 Relatório: ZeroClaw + ConvexBridge como Serviço
**Data:** 2026-02-26  
**Objetivo:** Avaliar a viabilidade de substituir o nanobot (Python) pelo ZeroClaw (Rust) como runtime de agente, mantendo o ConvexBridge como serviço de infraestrutura compartilhado.

---

## 1. 🔍 O que pesquisar antes de decidir

### 1.1 Sobre o ZeroClaw
- [ ] Qual é a arquitetura interna do ZeroClaw? (AgentLoop, tool use, contexto)
- [ ] Como ele gerencia o ciclo de vida de uma task? (planejamento → execução → resultado)
- [ ] Ele já tem suporte nativo a **tool use** (function calling) com Claude/OpenAI?
- [ ] Como ele lida com **streaming** de respostas da LLM?
- [ ] Qual o modelo de **skills/plugins** dele? É compatível com scripts externos?
- [ ] Ele tem suporte a **múltiplos LLM providers** (Anthropic, OpenAI, Gemini, Ollama)?
- [ ] Qual o tamanho do binário compilado e consumo de RAM em produção?
- [ ] Tem suporte a **async/concorrência** nativa (Tokio)?
- [ ] Qual a maturidade do projeto? (versão, comunidade, issues abertos)
- [ ] Tem documentação de como estender/customizar o AgentLoop?

### 1.2 Sobre o ConvexBridge como serviço
- [ ] O Convex tem SDK oficial em Rust? (pesquisar no GitHub convex-dev)
- [ ] A API HTTP do Convex é totalmente documentada para reimplementação?
- [ ] Quais endpoints são usados pelo ConvexBridge atual? (queries, mutations, actions, subscriptions)
- [ ] O protocolo de **subscriptions** (realtime) do Convex usa WebSocket ou SSE?
- [ ] Existe algum projeto open source que já implementou cliente Convex em Rust ou Go?
- [ ] Qual o overhead de transformar o ConvexBridge em serviço gRPC vs REST local?
- [ ] Como gerenciar **autenticação e tokens** de forma segura no serviço?

### 1.3 Sobre protocolos de comunicação
- [ ] gRPC via `tonic` (Rust) — maturidade, complexidade de schema protobuf
- [ ] Alternativa: **JSON-RPC over Unix socket** — mais simples, zero latência de rede
- [ ] Alternativa: **MessagePack over TCP local** — binário sem schema
- [ ] Como o ZeroClaw faz IPC (inter-process communication) atualmente?
- [ ] Qual o overhead real de latência entre processo Rust → serviço Python local?

### 1.4 Sobre memória vetorial
- [ ] **Qdrant** — suporte a Rust nativo? Client oficial? Self-hosted vs cloud?
- [ ] **LanceDB** — escrito em Rust, embutível, sem servidor separado (ideal!)
- [ ] **sqlite-vss** — extensão SQLite para busca vetorial, ultra-leve
- [ ] **pgvector** — requer PostgreSQL, mais pesado mas mais robusto
- [ ] Como gerar embeddings sem depender de Python? (APIs: OpenAI, Voyage, Cohere)
- [ ] Como migrar o HISTORY.md atual para busca semântica sem perder compatibilidade com grep?

### 1.5 Sobre compatibilidade com o MC atual
- [ ] O schema do Convex precisaria de alterações para suportar agentes Rust?
- [ ] O campo `type: remote/local/rust` no registro do agente seria suficiente?
- [ ] Como o MC identificaria se o agente remoto está online? (heartbeat via ConvexBridge service)
- [ ] As skills atuais (Python scripts) continuariam funcionando via subprocess do ZeroClaw?
- [ ] O formato de mensagens na thread do Convex é agnóstico de linguagem?

---

## 2. ✅ Prós

### Performance
- **Startup <10ms** vs ~500ms do Python — crítico para agentes efêmeros/serverless
- **Memória ~5-20MB** vs ~100MB Python — viabiliza edge computing e hardware limitado
- **Concorrência real** com Tokio — múltiplos agentes no mesmo processo sem GIL
- **Binário único** — sem virtualenv, sem dependências, deploy trivial

### Arquitetura
- **ConvexBridge como serviço compartilhado** — uma conexão Convex para N agentes ZeroClaw
- **Separação de responsabilidades** — infraestrutura (bridge) vs lógica (agente)
- **Multi-DB nativo** — ZeroClaw pode falar com Qdrant, LanceDB, SQLite sem wrappers Python
- **Agnóstico de linguagem** — qualquer cliente que fale o protocolo pode usar o bridge

### Escalabilidade
- **Agentes remotos leves** — instalar em qualquer máquina com binário de 10-20MB
- **Memória semântica real** — busca vetorial substitui o grep no HISTORY.md
- **Sem runtime Python** — deploy em containers mínimos (scratch, distroless)

---

## 3. ❌ Contras

### Complexidade técnica
- **Sem SDK Convex oficial em Rust** — precisaria reimplementar o ConvexBridge do zero via HTTP
- **Protocolo de subscriptions** — WebSocket realtime do Convex é complexo de reimplementar
- **Dois ecossistemas** — manter Rust + Python aumenta a carga cognitiva do time
- **Skills em Python** — precisaria de bridge subprocess ou reescrever skills em Rust

### Risco de projeto
- **ZeroClaw é menos maduro** que o nanobot — risco de bugs e features faltando
- **Comunidade menor** — menos recursos, exemplos e suporte
- **Migração incremental complexa** — como rodar nanobot e ZeroClaw em paralelo no mesmo MC?
- **Tool use em Rust** — menos bibliotecas e exemplos que Python para function calling com LLMs

### Custo-benefício questionável
- **Gargalo real é a API do Claude** (~200-2000ms) — ganho de performance do Rust é marginal no tempo total
- **Reescrever o AgentLoop** — toda a lógica de planejamento, execução e retry precisaria ser portada
- **Debugging mais difícil** — Rust tem curva de aprendizado alta para quem não é da linguagem

---

## 4. ⚠️ Pontos de Tensão

### 4.1 Quem mantém o ConvexBridge service?
- Se o serviço Python cair, todos os agentes ZeroClaw ficam cegos
- Precisa de **supervisão de processo** (systemd, supervisord) e **health check**
- Estratégia de **failover** se o bridge service não responder

### 4.2 Compatibilidade de skills
- Skills atuais são scripts Python com SKILL.md
- ZeroClaw precisaria de um **skill runner** que execute subprocess Python
- Ou: definir um novo formato de skill agnóstico de linguagem (WASM?)

### 4.3 Sincronização de contexto
- O nanobot carrega MEMORY.md + HISTORY.md no início de cada sessão
- O ZeroClaw precisaria de um mecanismo equivalente — via ConvexBridge service ou leitura direta de arquivo?
- Com memória vetorial: quem gera os embeddings? (Python? API externa?)

### 4.4 Autenticação multi-máquina
- O ConvexBridge service exposto em rede local ou remota precisa de autenticação
- Token por máquina? mTLS? API key rotacionável?
- Risco: bridge service exposto sem auth vira vetor de ataque

### 4.5 Versioning e compatibilidade
- Se o schema do Convex mudar, o ConvexBridge service precisa ser atualizado
- ZeroClaw pode ficar desatualizado em relação ao schema do MC
- Estratégia de **versionamento do protocolo** entre bridge e agente

### 4.6 Onde fica a inteligência?
- No nanobot atual: AgentLoop (Python) decide quando chamar tools, quando parar, como planejar
- No ZeroClaw: essa lógica precisa existir em Rust — está implementada? É customizável?
- Risco de **regressão de capacidade** se o AgentLoop do ZeroClaw for menos sofisticado

---

## 5. 🗺️ Arquitetura proposta para validar

```
┌─────────────────────────────────────────────────────┐
│                  Mission Control UI                  │
│                  (Next.js, porta 4000)               │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│              Convex Cloud ☁️                         │
│         (tasks, messages, agents, steps)             │
└──────────────┬──────────────────────────────────────┘
               │
               │ HTTP/WebSocket
               ▼
┌──────────────────────────────┐
│   ConvexBridge Service       │  ← Python, roda local
│   (gRPC server, porta 50051) │    ou no servidor
│   ├── queries                │
│   ├── mutations              │
│   ├── subscriptions          │
│   └── health check           │
└──────┬───────────────────────┘
       │ gRPC (local)
       ├─────────────────────────────┐
       ▼                             ▼
┌─────────────┐             ┌─────────────────┐
│  ZeroClaw   │             │  ZeroClaw       │
│  (local)    │             │  (remoto)       │
│  Rust agent │             │  Rust agent     │
│  ~10MB RAM  │             │  ~10MB RAM      │
└──────┬──────┘             └────────┬────────┘
       │                             │
       ▼                             ▼
┌─────────────┐             ┌─────────────────┐
│  LanceDB    │             │  Qdrant         │
│  (vetorial) │             │  (vetorial)     │
└─────────────┘             └─────────────────┘
```

---

## 6. 📋 Perguntas-chave para o agente pesquisar

1. O ZeroClaw tem AgentLoop com tool use implementado? Como funciona?
2. Existe cliente Convex não-oficial em Rust ou Go? (GitHub search)
3. LanceDB embutível em Rust — é production-ready?
4. Qual o custo real de implementar gRPC server em Python com `grpcio`?
5. O ZeroClaw suporta execução de subprocess para skills externas?
6. Existe precedente de arquitetura "Rust agent + Python bridge" em projetos open source?
7. O protocolo de subscriptions do Convex é WebSocket puro ou tem protocolo proprietário?
8. Como o ZeroClaw gerencia memória de sessão hoje?

---

## 7. 💡 Recomendação preliminar

**Não substituir — complementar.**

A abordagem mais segura seria:
1. **Fase 1:** Transformar o ConvexBridge em serviço com API REST/gRPC local (sem ZeroClaw ainda)
2. **Fase 2:** Criar um agente ZeroClaw mínimo que consome o bridge service
3. **Fase 3:** Rodar nanobot e ZeroClaw em paralelo no mesmo MC, comparar
4. **Fase 4:** Migrar agentes gradualmente para ZeroClaw onde performance importa

Isso minimiza risco e permite validação incremental.

---

*Relatório gerado por Owl 🦉 — 2026-02-26*

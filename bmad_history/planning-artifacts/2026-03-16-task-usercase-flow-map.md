# Task User Case Flow Map

## Objetivo

Este documento mapeia o fluxo real de `tasks`, `executionPlan`, `steps`,
`review` e `@mentions` no estado atual do projeto.

O foco aqui e separar claramente:

- criacao de task comum
- criacao de task manual
- criacao de task de workflow
- diferenca entre `task` e `step`
- onde o Lead Agent atua
- onde o Lead Agent nao atua
- review de task
- mencao no chat vs delegacao operacional

## Entidades E Donos

### Task

`tasks` e a unidade de lifecycle principal.

- Store: `dashboard/convex/schema.ts`
- Mutacoes principais: `dashboard/convex/tasks.ts`
- Regras auxiliares:
  - `dashboard/convex/lib/taskMetadata.ts`
  - `dashboard/convex/lib/taskPlanning.ts`
  - `dashboard/convex/lib/taskStatus.ts`
  - `dashboard/convex/lib/taskReview.ts`
  - `dashboard/convex/lib/taskLifecycle.ts`

Campos que mudam o fluxo:

- `status`
- `assignedAgent`
- `executionPlan`
- `awaitingKickoff`
- `isManual`
- `workMode`
- `trustLevel`
- `reviewers`
- `sourceAgent`

### Step

`steps` sao unidades materializadas de execucao abaixo da task.

- Store: `dashboard/convex/schema.ts`
- Mutacoes principais: `dashboard/convex/steps.ts`
- Materializacao: `mc/contexts/planning/materializer.py`
- Dispatch: `mc/contexts/execution/step_dispatcher.py`

Campos que mudam o fluxo:

- `status`
- `assignedAgent`
- `blockedBy`
- `parallelGroup`
- `workflowStepType`
- `reviewSpecId`
- `onRejectStepId`

### Thread / Conversa

O journal de conversa da task mora em `messages`.

- Store: `dashboard/convex/messages.ts`
- Classificacao de intent: `mc/contexts/conversation/intent.py`
- Pipeline unificado: `mc/contexts/conversation/service.py`
- Mencoes: `mc/contexts/conversation/mentions/watcher.py`
- Execucao de mencao: `mc/contexts/conversation/mentions/handler.py`

## Regra Basica: Task Nao E Step

### O que a task representa

`task` representa a intencao completa do usuario e seu lifecycle top-level:

- inbox
- planning
- assigned
- in_progress
- review
- done
- crashed

Ela pode existir:

- sem plano
- com `executionPlan` ainda nao materializado
- com `steps` materializados

### O que o step representa

`step` representa uma unidade concreta de trabalho dentro da task.

Um step:

- nasce do `executionPlan`
- tem dependencia propria
- tem agente proprio
- pode ser manual, gate, humano ou automatizado

### Consequencia importante

Muita ambiguidade vem daqui:

- `task.status = review` nao significa que existe um `review step`
- `workflowStepType = review` nao e a mesma coisa que `task.status = review`
- uma task pode estar em `review` sem nenhum step do tipo `review`
- uma task pode estar em `in_progress` enquanto um step esta em `waiting_human`

## User Case 1: Criacao De Task Comum

### Entrada

Normalmente passa por `tasks.create` e cai em `taskMetadata.createTask`.

Comportamento:

- cria a task sempre em `status = inbox`
- se nao for manual, preserva `assignedAgent` opcional
- define `trustLevel`
- define `supervisionMode`
- escolhe `boardId` default se nao vier um explicito

### Roteamento inicial

Quem pega isso e `mc/runtime/workers/inbox.py`.

#### Caso A: task comum sem `assignedAgent`

Fluxo:

1. task nasce em `inbox`
2. `InboxWorker` pode gerar auto-title
3. task vai para `planning`
4. `PlanningWorker` chama o `TaskPlanner`
5. o planner gera `executionPlan`
6. dependendo do modo:
   - `autonomous`: materializa e ja despacha
   - `supervised`: vai para `review` com `awaitingKickoff = true`

### Caso B: task comum com `assignedAgent`

Fluxo:

1. task nasce em `inbox`
2. `InboxWorker` nao passa pelo planner primeiro
3. task vai para `assigned`

Esse caminho e importante:

- ele nao representa um plano multi-step
- ele representa uma atribuicao direta para um agente
- esse caminho e mais parecido com "delegacao direta" do que com "orquestracao"

### Diferenca real entre task comum planejada vs direta

Task comum planejada:

- usa Lead Agent
- gera `executionPlan`
- normalmente vira varios `steps`

Task comum atribuida direto:

- nao precisa do Lead Agent para comecar
- pode funcionar como uma task orientada a um unico agente

## User Case 2: Criacao De Task Manual

### Entrada

Tambem nasce via `tasks.create`, mas com `isManual = true`.

### Diferencas de comportamento

Em `taskMetadata.createTask`:

- `assignedAgent` e removido
- `trustLevel` vira `autonomous`
- `supervisionMode` vira `autonomous`
- reviewers nao sao preservados

Em `InboxWorker`:

- tasks manuais sao ignoradas
- nao ha auto-roteamento para `planning` nem para `assigned`

### Como a task manual anda

Ela depende de acoes explicitas do usuario:

- salvar/editar `executionPlan`
- `startManualInboxTask`
- `manualMove`
- `clearTaskExecutionPlan`

### Implicacao

Task manual nao entra no pipeline normal do Lead Agent por default.
Ela e controlada mais pelo dashboard do que pelo runtime automatico.

## User Case 3: Criacao De Task De Workflow

### Entrada

Esse fluxo entra por `tasks.launchMission`, que chama
`dashboard/convex/lib/squadMissionLaunch.ts`.

### O que acontece

1. valida `squadSpec` publicado
2. valida `workflowSpec` publicado
3. resolve agentes reais a partir de `agentIds`
4. compila o workflow para um `executionPlan`
5. grava task com:
   - `status = planning`
   - `workMode = ai_workflow`
   - `executionPlan.generatedBy = workflow`
   - `squadSpecId`
   - `workflowSpecId`

### Diferenca central para task comum

Task comum:

- o plano nasce do Lead Agent
- `generatedBy = lead-agent`

Task de workflow:

- o plano nasce do compiler de workflow
- `generatedBy = workflow`
- o planner LLM deve ser pulado

### Onde isso e garantido

Existe defesa em mais de uma camada:

- `mc/runtime/workers/planning.py`
- `mc/runtime/workers/inbox.py`

Ambos tentam impedir que uma task `ai_workflow` com plano `generatedBy=workflow`
seja sobrescrita por um plano do Lead Agent.

### Kickoff e provenance

Quando materializada, a task de workflow pode criar `workflowRuns` com o
mapeamento:

- `workflow step id`
- `real Convex step id`

Isso acontece em `mc/runtime/workers/kickoff.py`.

## User Case 4: Como O Lead Agent Atua

### O que o Lead Agent faz

O Lead Agent e orquestrador.

Ele atua em:

- planejamento da task
- geracao de `executionPlan`
- negociacao de plano via chat
- postagem de `lead_agent_plan`
- postagem de `lead_agent_chat`

Arquivos principais:

- `mc/contexts/planning/planner.py`
- `mc/runtime/workers/planning.py`
- `mc/contexts/planning/negotiation.py`
- `dashboard/convex/messages.ts`

### O que o Lead Agent explicitamente nao faz

Ele nao executa steps.

Sinais concretos no codigo:

- `planner.py`: "NEVER assign lead-agent to any step"
- `mentions/handler.py`: `@lead-agent` e bloqueado
- `step_dispatcher.py`: se um step vier para `lead-agent`, ele e rerotado para `nanobot`

### Onde falar com o Lead Agent do jeito canonico

O caminho canonico nao e `@lead-agent`.

O caminho canonico e:

- task em `review` com `awaitingKickoff = true`
- ou task em `in_progress` com `executionPlan`
- mensagem classificada como `plan_chat`

Nesse caso o pipeline vai para `handle_plan_negotiation`.

## User Case 5: Como O Plano Vira Steps

### Materializacao

Quando existe `executionPlan`, o materializador cria `steps` reais em Convex.

Regras:

- cada `tempId` vira um `step`
- `blockedByTempIds` vira `blockedBy` real
- metadata de workflow e preservada quando existir

### Kickoff

Existem dois caminhos principais:

- autonomo: o planning worker ja materializa e dispara
- supervisionado: vai para `review + awaitingKickoff`, depois `approveAndKickOff`

### Papel do dispatcher

`StepDispatcher`:

- so despacha quando `task.status == in_progress`
- pega `steps` em `assigned`
- agrupa por `parallelGroup`
- executa grupos em paralelo
- ao final pode promover a task para:
  - `review`
  - `done`
  - `crashed`

### Reconciliacao task <- step

`steps.updateStatus` tambem pode reconciliar a task pai.

Entao hoje a task pode ser alterada por dois eixos:

- workers Python
- mutacoes Convex em `steps.ts`

Esse e um dos hotspots de ambiguidade.

## User Case 6: Diferenca Entre Step Humano, Gate E Step Normal

### Step normal

- vai para `running`
- executor real e chamado

### Step humano / gate

Em `step_dispatcher.py`:

- `assignedAgent == human`
- ou `workflowStepType in (human, checkpoint)`

esses passos nao executam automaticamente.

Comportamento:

- gate de workflow vai para `waiting_human`
- step humano fica aguardando acao humana

Depois o dashboard usa:

- `acceptHumanStep`
- `manualMoveStep`

### Ponto de confusao

`task.status = in_progress` pode coexistir com `step.status = waiting_human`.
Ou seja: a task nao esta necessariamente "rodando autonomamente" so porque esta
em `in_progress`.

## User Case 7: Review De Task

### Existem tres reviews diferentes no sistema

#### 1. Review de plano antes do kickoff

Condicao:

- `task.status = review`
- `awaitingKickoff = true`

Significado:

- plano pronto
- usuario ainda nao aprovou o inicio

Acao canonica:

- `approveAndKickOff`

#### 2. Review top-level apos execucao

Condicao:

- dispatcher terminou todos os steps
- `resolve_completion_status` decide review ou done

Significado:

- execucao terminou
- pode faltar aprovacao explicita

Mutacoes relevantes:

- `approve`
- `deny`
- `returnToLeadAgent`

#### 3. Review step dentro de workflow

Isso e um `step` com metadata:

- `workflowStepType = review`
- `reviewSpecId`
- `onRejectStepId`

Isso nao e a mesma coisa que `task.status = review`.

### O que acontece em cada acao

`approve`:

- so vale para task em `review`
- task vai para `done`
- steps do plano podem ser marcados como `completed`

`deny`:

- task fica em `review`
- grava feedback e atividade

`returnToLeadAgent`:

- task volta para `inbox`
- `assignedAgent` e limpo
- thread e preservada

Esse ultimo caminho e importante:

- ele nao "manda para o Lead Agent" imediatamente
- ele recoloca a task no pipeline de intake
- depois os workers a recolocam em `planning` ou `assigned`

## User Case 8: Mensao No Chat Com @Agente

### Entrada canonica

`postMentionMessage`

Esse caminho:

- grava a mensagem do usuario
- grava atividade
- nao muda status da task
- nao muda `assignedAgent`
- nao limpa `executionPlan`

Depois o `MentionWatcher`:

- busca mensagens recentes do usuario
- detecta `@agent-name`
- chama o `ConversationService`
- classifica como `MENTION`
- executa `handle_all_mentions`

### O que a mencao realmente faz

Ela roda o agente mencionado como resposta de thread, com contexto de:

- task
- executionPlan resumido
- arquivos da task
- thread recente
- merged sources quando existir

E depois:

- posta uma resposta na thread

### O que a mencao nao faz

Ela nao:

- cria nova task
- cria step
- muda `assignedAgent`
- muda `task.status`
- transforma o agente mencionado em dono operacional da task

Essa e uma das ambiguidades centrais do produto hoje:

`@agente` parece delegacao, mas no codigo atual e uma interacao one-shot de thread.

## User Case 9: Delegacao Operacional Via Thread

### Entrada canonica

`sendThreadMessage`

Esse e o fluxo que de fato muda o ownership operacional.

Comportamento:

1. grava mensagem do usuario
2. se a task nao for manual:
   - muda `status` para `assigned`
   - define `assignedAgent`
   - grava `previousStatus`
   - limpa `executionPlan`
   - limpa `stalledAt`

### Consequencia

Esse fluxo nao e "conversa".
Esse fluxo e "reatribuicao operacional".

Em outras palavras:

- `postMentionMessage` = pergunta/comando na thread
- `sendThreadMessage` = reassignment real da task

### Ponto de bug provavel

Se a UI ou o usuario trata `@agent` como se fosse equivalente a `sendThreadMessage`,
vai haver discrepancia entre:

- expectativa mental do usuario
- status/assignedAgent reais em Convex

## User Case 10: Follow-up Sem @mention

O `ConversationIntentResolver` classifica um texto sem mencao como `FOLLOW_UP`
quando:

- status esta em `assigned`, `in_progress`, `review` ou `retrying`
- existe `assignedAgent`

Mas o `ConversationService` nao executa esse follow-up por conta propria.
Ele apenas devolve o intent para o caller.

Isso significa que existe uma camada de ambiguidade extra:

- o intent existe
- mas o roteamento efetivo depende do caller

## Diferencas Importantes Entre Os Tipos De Task

### Task comum automatica

- nasce em `inbox`
- vai para `planning` ou `assigned`
- pode usar Lead Agent
- pode gerar `executionPlan`
- pode virar varios `steps`

### Task manual

- nasce em `inbox`
- inbox worker ignora
- usuario controla o ciclo
- nao entra no pipeline automatico do Lead Agent por default

### Task de workflow

- nasce em `planning`
- ja tem `executionPlan` compilado
- `generatedBy = workflow`
- deve pular o planner LLM
- pode gerar `workflowRuns`

## Mapa Curto: Onde Ha Ambiguidade Hoje

### 1. Mencao vs delegacao

Esses dois fluxos parecem proximos para o usuario, mas sao muito diferentes:

- `postMentionMessage`: thread response
- `sendThreadMessage`: reassignment e limpeza de plano

### 2. Review top-level vs review step

`task.status = review` e `workflowStepType = review` nao significam a mesma coisa.

### 3. Task status governado em dois lugares

A task pode ser alterada por:

- workers Python
- mutacoes Convex
- reconciliacao vinda de `steps.updateStatus`

### 4. Contrato de transicao divergente

`dashboard/convex/lib/taskLifecycle.ts` permite `inbox -> in_progress`,
mas o contrato shared em `shared/workflow/workflow_spec.json` nao.

### 5. Return to lead agent nao e dispatch direto para lead agent

`returnToLeadAgent` volta a task para `inbox`.
Quem decide o proximo dono operacional depois disso e o pipeline de runtime.

## Sintese Final

Se a pergunta for "quem esta trabalhando na task agora?", hoje a resposta depende
de olhar ao mesmo tempo:

- `task.status`
- `task.assignedAgent`
- `task.executionPlan`
- `task.awaitingKickoff`
- `task.isManual`
- `task.workMode`
- `steps[].status`
- `steps[].assignedAgent`
- se a mensagem do usuario entrou por `postMentionMessage` ou `sendThreadMessage`

Esse acoplamento explica por que bugs de fluxo de dados aparecem com facilidade:
o produto mistura no mesmo espaco mental coisas que no codigo sao bem diferentes:

- conversa
- delegacao
- planejamento
- kickoff
- review de task
- review step de workflow
- task manual
- task de workflow

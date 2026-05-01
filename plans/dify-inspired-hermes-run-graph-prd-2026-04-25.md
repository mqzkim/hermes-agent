# Dify 기반 Hermes Run Graph / Agent Board PRD

> 상태: 초안 v1  
> 작성일: 2026-04-25  
> 관련 분석: `plans/dify-orchestration-lessons-2026-04-25.md`  
> 대상 repo: `/home/mqz/.hermes/hermes-agent`

## 0. 문서 목적

이 PRD는 Dify의 production-grade agent orchestration 패턴을 Hermes Agent에 이식하기 위한 제품 요구사항 문서다. 구현 상세보다 **무엇을, 왜, 어떤 기준으로 완성으로 볼지**를 정의한다.

핵심 목표는 Hermes를 단순 대화형 tool-calling agent에서 다음 형태로 확장하는 것이다.

- 실행 전체를 `Run → Node → Event → Artifact`로 추적한다.
- subagent, tool call, model call, cron, human input, artifact 갱신을 같은 실행 그래프 안에서 본다.
- Agent Board/TUI/Gateway가 고대역폭 artifact UI를 통해 실행을 관찰·제어한다.
- benchmark harness가 transcript가 아니라 구조화된 run graph와 artifact snapshot을 평가한다.

---

## 1. Index

### 1.1 PRD Index

- [0. 문서 목적](#0-문서-목적)
- [1. Index](#1-index)
- [2. 배경과 근거](#2-배경과-근거)
- [3. 제품 비전](#3-제품-비전)
- [4. 사용자/운영자 페르소나](#4-사용자운영자-페르소나)
- [5. 문제 정의](#5-문제-정의)
- [6. 목표와 비목표](#6-목표와-비목표)
- [7. 제품 범위](#7-제품-범위)
- [8. 핵심 개념 모델](#8-핵심-개념-모델)
- [9. 기능 요구사항](#9-기능-요구사항)
- [10. 비기능 요구사항](#10-비기능-요구사항)
- [11. UX / Agent Board 요구사항](#11-ux--agent-board-요구사항)
- [12. Benchmark Harness 요구사항](#12-benchmark-harness-요구사항)
- [13. 데이터/이벤트 계약](#13-데이터이벤트-계약)
- [14. 마일스톤](#14-마일스톤)
- [15. 성공 지표](#15-성공-지표)
- [16. 릴리즈 게이트](#16-릴리즈-게이트)
- [17. 리스크와 대응](#17-리스크와-대응)
- [18. PRD 체크리스트](#18-prd-체크리스트)

### 1.2 수행 Index

| 단계 | 이름 | 산출물 | 완료 기준 |
|---|---|---|---|
| PRD-01 | 요구사항 확정 | 본 PRD 승인 | 목표/비목표/범위가 모순 없음 |
| PRD-02 | 개념 모델 확정 | Run/Node/Event/Artifact 용어집 | 모든 구현 문서가 같은 용어 사용 |
| PRD-03 | MVP 범위 확정 | P0/P1/P2 범위표 | P0만으로도 가치 검증 가능 |
| PRD-04 | UI 요구 확정 | Agent Board 화면 요구 | run graph, artifact, decision log가 한 화면에 연결됨 |
| PRD-05 | Harness 요구 확정 | benchmark 요구 | oracle이 node/artifact 기준으로 동작 가능 |
| PRD-06 | 릴리즈 게이트 확정 | acceptance checklist | 구현 plan과 1:1 대응 |

---

## 2. 배경과 근거

### 2.1 Dify에서 확인한 패턴

Dify는 실행 시스템을 다음 계약으로 분리한다.

- 그래프 DSL: `nodes[]`, `edges[]`, node `type/version`
- 런타임 상태: `GraphRuntimeState`, `VariablePool`, `GraphEngine`
- 노드 팩토리: `node_factory.py`에서 registry bootstrap
- 실행 레이어: persistence, observability, quota, limits
- 이벤트 변환: graph event를 queue/UI event와 execution log로 변환
- workflow-as-tool: workflow를 다시 tool runtime으로 호출
- single-node debug: 특정 node/loop/iteration 단독 실행

근거 파일:

- Dify: `api/core/workflow/node_factory.py`
- Dify: `api/core/workflow/workflow_entry.py`
- Dify: `api/core/app/apps/workflow/app_runner.py`
- Dify: `api/core/app/apps/workflow_app_runner.py`
- Dify: `api/core/app/workflow/layers/persistence.py`
- Dify: `api/core/app/workflow/layers/observability.py`
- Dify: `api/core/tools/workflow_as_tool/tool.py`
- Dify: `web/app/components/workflow/types.ts`

### 2.2 Hermes의 현재 강점

- `tools/registry.py`: tool self-registration과 toolset 기반 필터링
- `model_tools.py`: tool discovery, async bridge, function call dispatch
- `run_agent.py`: provider adapter와 tool-calling loop
- `tools/delegate_tool.py`: subagent 실행, active subagent registry, interrupt/pause spawn
- `hermes_state.py`: SQLite SessionDB, WAL, FTS5 session search
- `gateway/`, `ui-tui/`, `tui_gateway/`: multi-platform/control surface 기반

### 2.3 Hermes의 현재 공백

- tool/model/subagent 실행이 하나의 구조화된 run graph로 저장되지 않는다.
- artifact와 final answer가 분리된 제품 단위로 관리되지 않는다.
- event stream이 UI/benchmark/harness에서 재사용 가능한 안정 계약이 아니다.
- 특정 tool call/subagent/artifact node만 replay하는 표준 경로가 없다.
- benchmark 평가가 run graph/node/artifact 단위로 축적되기 어렵다.

---

## 3. 제품 비전

Hermes Run Graph는 Hermes 내부의 모든 실행을 구조화된 그래프로 포착하는 orchestration substrate다.

최종 경험:

> 사용자는 Agent Board에서 하나의 실행을 펼쳐 보고, 어떤 agent가 어떤 tool을 호출했고, 어떤 artifact를 만들었고, 어떤 결정이 왜 내려졌고, 어디서 실패했는지 즉시 확인한다. 실패 node만 재실행하거나 다른 model/subagent로 replay할 수 있다. benchmark harness는 이 구조화된 실행 로그를 근거로 평가·회귀 분석한다.

---

## 4. 사용자/운영자 페르소나

### 4.1 Power User / Operator

- Discord/Gateway에서 Hermes를 여러 채널·에고·세션으로 운영한다.
- 긴 작업을 subagent와 cron으로 돌린다.
- 요구: 현재 실행 상태, 실패 지점, 비용/토큰/시간, artifact 변화를 즉시 보고 싶다.

### 4.2 Harness Builder

- benchmark repo와 자동 평가 harness를 만든다.
- 요구: transcript가 아니라 node별 입력/출력/오류/artifact snapshot/oracle result가 필요하다.

### 4.3 Agent UI Designer

- Legora식 고대역폭 artifact UI를 설계한다.
- 요구: run tree, decision log, working document, table, checklist가 같은 event stream에서 공급되어야 한다.

### 4.4 Coding Agent Implementer

- Hermes core를 수정한다.
- 요구: 작은 task, exact file path, tests, migration path, backward compatibility가 필요하다.

---

## 5. 문제 정의

### 5.1 관찰성 문제

현재 Hermes는 개별 tool result와 대화 메시지는 남기지만, 실행의 의미 구조가 약하다. 예를 들어 “이 subagent가 만든 분석표가 어떤 tool call과 어떤 model decision에서 나왔는지”를 안정적으로 재구성하기 어렵다.

### 5.2 제어성 문제

긴 실행 중 특정 child/subagent/tool call만 pause, interrupt, replay, resume하는 기능이 제한적이다.

### 5.3 Harness 문제

benchmark에서는 pass/fail뿐 아니라 어떤 node가 실패했는지, oracle이 어떤 artifact 버전을 평가했는지, retry가 성능을 개선했는지 알아야 한다.

### 5.4 UI 문제

채팅 transcript는 정보 밀도가 낮다. 복잡한 agent collaboration에서는 작업트리, 결정로그, artifact diff, node status가 동시에 보여야 한다.

---

## 6. 목표와 비목표

### 6.1 목표

- G1. 모든 Hermes 실행을 `Run → Node → Event`로 정규화한다.
- G2. model call, tool call, subagent, cron, human input, artifact update를 같은 graph에 기록한다.
- G3. SQLite에 영속 저장하고, UI/API에서 조회 가능하게 한다.
- G4. Agent Board/TUI가 run graph와 artifact 상태를 실시간 또는 준실시간으로 표시한다.
- G5. benchmark harness가 node/artifact 단위 평가를 수행할 수 있게 한다.
- G6. 기존 session/message 저장과 호환성을 유지한다.

### 6.2 비목표

- NG1. Dify의 `graphon` 패키지를 그대로 도입하지 않는다.
- NG2. 초기 MVP에서 완전한 visual workflow builder를 만들지 않는다.
- NG3. 모든 기존 tool을 즉시 typed output으로 재작성하지 않는다.
- NG4. 초기에 distributed worker scheduler를 새로 만들지 않는다.
- NG5. OpenTelemetry exporter는 필수가 아니다. 내부 event schema가 우선이다.

---

## 7. 제품 범위

### 7.1 P0 MVP

- Run/Node/Event dataclass 또는 Pydantic 모델
- RunLayer protocol
- In-memory event bus
- SQLite persistence
- `run_agent.py` model call/tool call instrumentation
- `tools/delegate_tool.py` subagent node 연결
- 최소 조회 API 또는 Python accessor
- 테스트 커버리지: event model, persistence, instrumentation, delegate 연결

### 7.2 P1

- Artifact 모델과 versioning
- Agent Board/TUI run graph panel
- single-node replay skeleton
- workflow-as-tool / saved harness-as-tool skeleton
- variable selector 기반 typed output 일부 도입

### 7.3 P2

- human input pause/resume state
- trigger node 통합(cron/gateway/webhook)
- OTel export
- benchmark dashboard
- full artifact diff/replay

---

## 8. 핵심 개념 모델

### 8.1 Run

하나의 사용자 요청, cron 실행, gateway message 처리, batch/harness case 실행을 대표한다.

필수 속성:

- `run_id`
- `session_id`
- `source`
- `root_goal`
- `status`
- `started_at`, `ended_at`
- `model`, `provider`
- `parent_run_id` optional
- `metadata`

### 8.2 Node

Run 안의 실행 단위다.

초기 node type:

- `agent_turn`
- `model_call`
- `tool_call`
- `subagent`
- `artifact`
- `decision`
- `human_input`
- `cron_job`
- `benchmark_case`

필수 속성:

- `node_id`
- `run_id`
- `parent_node_id`
- `node_type`
- `title`
- `status`
- `started_at`, `ended_at`
- `inputs_json`
- `outputs_json`
- `error`
- `metadata_json`

### 8.3 Event

Run/Node 상태 변화의 append-only record다.

초기 event type:

- `run_started`
- `run_succeeded`
- `run_failed`
- `run_paused`
- `run_stopped`
- `node_started`
- `node_succeeded`
- `node_failed`
- `node_retry`
- `model_request`
- `model_response`
- `tool_invocation`
- `tool_result`
- `subagent_spawned`
- `subagent_completed`
- `artifact_created`
- `artifact_updated`
- `decision_recorded`
- `human_input_requested`
- `human_input_received`

### 8.4 Artifact

Final answer와 별도로 관리되는 장기 작업 산출물이다.

초기 artifact type:

- `document`
- `table`
- `checklist`
- `decision_log`
- `task_tree`
- `benchmark_report`
- `code_patch`
- `file_reference`

### 8.5 Variable Selector

Node output과 artifact field를 참조하는 경로다.

예:

- `@run.status`
- `@node.<node_id>.outputs.stdout`
- `@tool.terminal.exit_code`
- `@subagent.<id>.summary`
- `@artifact.<id>.versions[-1].content`

---

## 9. 기능 요구사항

### FR-01 Run 생성

사용자 요청, cron 실행, delegated child run, benchmark case 시작 시 Run을 생성해야 한다.

Acceptance:

- [ ] `run_id`가 모든 node/event에 전파된다.
- [ ] 기존 `session_id`와 연결된다.
- [ ] parent/child run 관계를 저장할 수 있다.

### FR-02 Node lifecycle 기록

각 model call/tool call/subagent 실행은 node로 기록되어야 한다.

Acceptance:

- [ ] node start/end event가 있다.
- [ ] success/failure status가 저장된다.
- [ ] duration 계산이 가능하다.
- [ ] error message와 structured metadata를 저장한다.

### FR-03 Event append-only 저장

모든 중요한 상태 변화는 event로 저장한다.

Acceptance:

- [ ] event order가 timestamp와 sequence로 안정적이다.
- [ ] event payload는 JSON 직렬화 가능하다.
- [ ] event 저장 실패가 agent 실행을 망가뜨리지 않는다. 단, warning log는 남긴다.

### FR-04 Layer hook

실행 lifecycle에 외부 레이어를 붙일 수 있어야 한다.

Acceptance:

- [ ] `RunLayer` protocol이 있다.
- [ ] 여러 layer가 순서대로 호출된다.
- [ ] layer 예외는 격리된다.
- [ ] persistence layer가 event를 저장한다.

### FR-05 Subagent graph 연결

`delegate_task`의 child agent는 parent run graph의 subagent node로 표현되어야 한다.

Acceptance:

- [ ] subagent id, parent id, depth, goal, model, tool_count를 node metadata로 저장한다.
- [ ] child completion 시 summary, status, output tail이 저장된다.
- [ ] interrupt/pause 상태가 node status에 반영된다.

### FR-06 Artifact update 기록

문서/표/checklist/decision log가 생성·갱신될 때 artifact event를 기록할 수 있어야 한다.

Acceptance:

- [ ] artifact id와 version id가 있다.
- [ ] artifact update가 어느 node에서 발생했는지 연결된다.
- [ ] artifact snapshot 조회가 가능하다.

### FR-07 조회 API

TUI/Gateway/Agent Board가 run graph를 조회할 수 있어야 한다.

Acceptance:

- [ ] 최근 run list
- [ ] run detail
- [ ] node list/tree
- [ ] event stream/tail
- [ ] artifact list/version

### FR-08 Replay 준비

초기에는 완전 replay가 아니어도 replay에 필요한 입력/출력/환경 metadata를 저장해야 한다.

Acceptance:

- [ ] tool name과 arguments 저장
- [ ] model/provider/model parameters 저장
- [ ] subagent goal/context/toolsets 저장
- [ ] file/workdir/task_id metadata 저장

---

## 10. 비기능 요구사항

### NFR-01 호환성

- 기존 SessionDB schema와 session search 기능을 깨지 않아야 한다.
- migration은 idempotent해야 한다.

### NFR-02 성능

- event 저장은 agent loop 체감 지연을 크게 늘리지 않아야 한다.
- SQLite lock contention은 기존 `SessionDB._execute_write` 패턴을 따른다.

### NFR-03 안정성

- instrumentation 실패는 best-effort로 처리한다.
- event payload가 너무 크면 truncate 또는 external storage reference를 사용한다.

### NFR-04 보안/프라이버시

- secrets/API keys는 payload에 그대로 저장하지 않는다.
- tool input/output redaction hook을 둔다.

### NFR-05 테스트 가능성

- in-memory/temp SQLite DB로 unit test가 가능해야 한다.
- 외부 API 호출 없이 instrumentation test가 가능해야 한다.

---

## 11. UX / Agent Board 요구사항

### 11.1 필수 화면 구성

- Run Header
  - status, duration, model/provider, cost/token, source
- Run Tree
  - agent_turn/tool_call/subagent/artifact/human_input node
- Event Timeline
  - ordered event stream
- Artifact Pane
  - document/table/checklist/decision log
- Inspector
  - selected node input/output/error/metadata
- Controls
  - interrupt, pause spawn, resume, replay selected node(초기 disabled 가능)

### 11.2 UX Acceptance

- [ ] 사용자는 실패한 node를 5초 안에 찾을 수 있다.
- [ ] 사용자는 subagent tree와 output tail을 한 화면에서 볼 수 있다.
- [ ] 사용자는 final answer와 artifact를 구분해서 볼 수 있다.
- [ ] 사용자는 decision log에서 model/tool 선택 이유를 확인할 수 있다.

---

## 12. Benchmark Harness 요구사항

### 12.1 평가 단위

- run-level oracle
- node-level oracle
- artifact-level oracle
- regression comparison

### 12.2 필요한 데이터

- task prompt/context
- model/provider
- toolsets
- tool calls and outputs
- subagent summaries
- artifacts and versions
- errors/retries
- timing/cost/token

### 12.3 Acceptance

- [ ] benchmark case가 `run_id`를 산출한다.
- [ ] oracle result가 artifact 또는 node에 연결된다.
- [ ] 실패 원인이 transcript grep이 아니라 node status/error로 식별된다.
- [ ] 회귀 비교가 artifact diff와 node duration/cost 차이를 보여준다.

---

## 13. 데이터/이벤트 계약

### 13.1 Status enum

Run/Node 공통:

- `pending`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `paused`
- `partial_succeeded`

### 13.2 Event payload 원칙

- JSON serializable
- secret redacted
- 64KB 이상 payload는 저장 전략 명시
- schema version 포함

### 13.3 Backward compatibility

- 기존 `sessions`, `messages`, FTS schema는 유지한다.
- 새 테이블은 additive migration만 사용한다.
- 기존 code path는 run graph가 disabled여도 동일 동작해야 한다.

---

## 14. 마일스톤

### M0: 문서/계약 확정

- PRD
- implementation plan
- event schema draft
- DB schema draft

### M1: Core Event MVP

- `agent/run_events.py`
- `agent/run_layers.py`
- `agent/run_graph.py`
- in-memory event sink
- unit tests

### M2: Persistence MVP

- SessionDB schema migration
- save/list/get APIs
- tests

### M3: Agent Loop Instrumentation

- model call node
- tool call node
- failure event
- tests with mocked model/tool

### M4: Delegate Integration

- subagent node
- child output tail
- active registry bridge
- interrupt status

### M5: UI/API Read Surface

- TUI gateway accessor or web endpoint
- run tree JSON
- event tail JSON

### M6: Artifact MVP

- artifact model
- decision log artifact
- benchmark report artifact

### M7: Harness MVP

- benchmark case creates run graph
- oracle result stored as artifact/node metadata

---

## 15. 성공 지표

### 제품 지표

- 긴 작업에서 실패 node 식별 시간 5초 이하
- subagent 실행의 parent-child 관계 100% 기록
- P0 instrumented tool call의 start/end event 100% 기록
- benchmark case별 run_id/artifact snapshot 100% 생성

### 개발 지표

- 새 core modules coverage 90% 이상
- SessionDB migration idempotency test 통과
- 기존 `tests/test_hermes_state.py` 통과
- delegate 관련 기존 tests 통과

---

## 16. 릴리즈 게이트

### P0 릴리즈 게이트

- [ ] Run/Node/Event model이 freeze된 schema version을 갖는다.
- [ ] SQLite migration이 기존 DB에서 안전하게 동작한다.
- [ ] `run_agent.py`에서 model/tool call event가 기록된다.
- [ ] `delegate_task` child가 subagent node로 기록된다.
- [ ] 조회 API로 최근 run과 node/event list를 볼 수 있다.
- [ ] 모든 신규 unit test 통과.
- [ ] 기존 session search regression 없음.

### P1 릴리즈 게이트

- [ ] artifact versioning 가능.
- [ ] Agent Board/TUI에서 run tree와 artifact pane 표시.
- [ ] selected node replay skeleton 동작.
- [ ] benchmark oracle result가 node/artifact에 연결됨.

---

## 17. 리스크와 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| `run_agent.py`가 매우 커서 instrumentation이 취약 | 회귀 위험 | thin adapter/context manager로 최소 patch |
| SQLite write contention | gateway/TUI freeze | 기존 `_execute_write` jitter retry 재사용 |
| payload 과대 저장 | DB bloating | payload size cap + artifact/file reference |
| secret leakage | 보안 위험 | redaction layer 필수 |
| UI 먼저 만들면 schema 흔들림 | 재작업 | P0는 schema/persistence 우선 |
| Dify식 graph engine 과도 도입 | 복잡도 증가 | graphon 미도입, Hermes-native thin contracts |

---

## 18. PRD 체크리스트

### 18.1 요구사항 체크리스트

- [ ] P0/P1/P2 범위가 분리되어 있다.
- [ ] 목표와 비목표가 명확하다.
- [ ] Dify 근거 파일이 연결되어 있다.
- [ ] Hermes 적용 대상 파일이 식별되어 있다.
- [ ] UI/benchmark 요구가 모두 포함되어 있다.
- [ ] 릴리즈 게이트가 테스트 가능한 문장이다.

### 18.2 구현 준비 체크리스트

- [ ] implementation plan이 본 PRD의 FR/NFR과 매핑된다.
- [ ] DB migration 전략이 있다.
- [ ] rollback/disable 전략이 있다.
- [ ] secrets redaction 전략이 있다.
- [ ] 기존 test regression 범위가 있다.

### 18.3 승인 체크리스트

- [ ] P0 MVP만으로도 Hermes 운영 가치가 있다.
- [ ] P1/P2가 P0 schema를 깨지 않고 확장된다.
- [ ] Agent Board 방향과 충돌하지 않는다.
- [ ] benchmark harness 방향과 충돌하지 않는다.

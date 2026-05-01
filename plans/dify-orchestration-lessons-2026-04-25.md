# Dify 오케스트레이션 분석: Hermes 적용 후보

- 분석 대상: `langgenius/dify` main, commit `f00512d`
- 로컬 경로: `/tmp/hermes-repo-analysis/dify`
- 비교 대상 Hermes: `/home/mqz/.hermes/hermes-agent`, commit `e655789c`

## 핵심 결론

Dify의 강점은 “모델 호출 루프” 자체가 아니라, 워크플로우 실행을 다음 계약으로 쪼갠 점이다.

1. 그래프 DSL: `nodes[]`, `edges[]`, node type/version, variable selector
2. 런타임: `GraphRuntimeState`, `VariablePool`, `GraphEngine`, `CommandChannel`
3. 노드 팩토리/레지스트리: built-in + 제품 로컬 노드의 self-registration
4. 레이어: persistence, observability, quota, execution limits, pause state
5. 이벤트 변환: GraphEngineEvent → UI/queue event → run/node execution log
6. 워크플로우-as-tool: 워크플로우를 다시 tool runtime으로 호출
7. single-node / loop / iteration debug runner

Hermes는 이미 강한 tool registry, gateway, subagent, cron, terminal harness를 갖고 있지만, 현재 중심 추상화는 `AIAgent.run_conversation()`의 선형 tool-calling loop와 `delegate_task`의 병렬 child-agent 실행이다. Dify식 그래프/레이어/이벤트 계약을 얇게 도입하면 Legora식 Agent Board와 benchmark harness를 production-grade로 밀어올릴 수 있다.

## 근거 파일

### Dify backend

- `api/core/workflow/node_factory.py`
  - `register_nodes()`가 `graphon.nodes` + `core.workflow.nodes`를 import해 노드 self-registration을 강제한다.
  - `DifyGraphInitContext`로 graph init에 필요한 제품 컨텍스트를 명시적으로 포장한다.
  - `resolve_workflow_node_class()`가 node type/version을 latest fallback으로 해석한다.

- `api/core/workflow/workflow_entry.py`
  - `WorkflowEntry`가 `GraphEngine`을 구성하고, `ExecutionLimitsLayer`, `LLMQuotaLayer`, `ObservabilityLayer`, `DebugLoggingLayer`를 attach한다.
  - `CommandChannel`을 주입하여 외부 중단/제어 가능성을 분리한다.

- `api/core/app/apps/workflow/app_runner.py`
  - `WorkflowAppRunner.run()`에서 system variables → `VariablePool` → `GraphRuntimeState` → `Graph` → `WorkflowEntry` 순으로 실행 컨텍스트를 만든다.
  - Redis command channel: `workflow:{task_id}:commands`.
  - `WorkflowPersistenceLayer`를 engine layer로 붙이고, GraphEngineEvent를 `_handle_event()`로 queue event에 매핑한다.

- `api/core/app/apps/workflow_app_runner.py`
  - Graph/node/loop/iteration/human-input/agent-log 이벤트를 UI가 소비할 queue event로 세밀하게 변환한다.
  - single-node 실행을 위한 variable preload, variable mapping, `skip_validation=True` debug graph 실행이 있다.

- `api/core/app/workflow/layers/persistence.py`
  - GraphEngineEvent를 workflow execution / node execution repository에 저장하는 event-sourced persistence layer.
  - presentation layer가 DB를 읽기만 하도록 실행 스레드 안에서 저장한다.

- `api/core/app/workflow/layers/observability.py`
  - GraphEngineLayer로 node span을 만들고 OTel context를 붙인다.
  - node type별 parser registry를 둔다.

- `api/core/tools/workflow_as_tool/tool.py`
  - Workflow를 Tool로 감싸 재귀적으로 호출하되 `workflow_call_depth`로 제한한다.
  - 파일/usage/output 변환 계약을 명시한다.

- `api/core/workflow/nodes/agent/agent_node.py`
  - agent strategy resolver, presentation provider, runtime support, message transformer를 생성자 주입한다.
  - agent plugin strategy 호출 결과를 node event stream으로 변환한다.

### Dify frontend

- `web/app/components/workflow/types.ts`
  - `BlockEnum`에 Start/End/LLM/Tool/Agent/Loop/HumanInput/Trigger 등 블록 타입이 명확히 선언되어 있다.
  - `CommonNodeType`, `CommonEdgeType`가 running status, retry index, loop/iteration membership 같은 UI state를 포함한다.

### Hermes 현재 구조

- `run_agent.py`
  - `AIAgent.run_conversation()` 중심의 synchronous tool-calling loop.

- `model_tools.py`, `tools/registry.py`
  - tool module self-registration, toolset filtering, sync/async bridge는 이미 Dify의 node registry와 유사한 강점이 있다.

- `tools/delegate_tool.py`
  - child agent registry, pause spawn, active subagent snapshot, interrupt가 이미 있음.
  - 하지만 graph/run/node event의 영속 모델과 UI artifact 계약은 아직 Dify만큼 분리되어 있지 않다.

## Hermes에 가져올 우선순위

### P0. Hermes Run Graph / Event Schema 도입

목표: 모든 agent run을 `run → node execution → event`로 정규화한다.

초기 노드 타입 후보:

- `agent_turn`: 모델 API 호출 1회
- `tool_call`: Hermes tool 실행 1회
- `subagent`: delegate child run
- `cron_job`: scheduled run
- `human_input`: clarify/approval/waiting state
- `artifact`: 문서/표/파일/결정로그 생성 또는 갱신
- `decision`: model/tool selection, fallback, retry decision

최소 이벤트:

- `run_started`, `run_succeeded`, `run_failed`, `run_stopped`, `run_paused`
- `node_started`, `node_succeeded`, `node_failed`, `node_retry`
- `text_chunk`, `tool_result`, `artifact_updated`, `agent_log`

Dify 근거: `workflow_app_runner.py`의 `_handle_event()`와 `queue_entities.py` 계열.

### P0. ExecutionLayer 인터페이스

Dify의 `GraphEngineLayer`처럼 Hermes에 run lifecycle hook을 둔다.

초기 레이어:

- `PersistenceLayer`: SQLite SessionDB에 run/node/event 저장
- `ObservabilityLayer`: OTel span 또는 내부 trace span
- `BudgetLayer`: iteration/tool/time/token budget
- `ArtifactLayer`: final answer와 별도로 artifact 문서/표/작업트리 갱신
- `ControlLayer`: interrupt/pause/resume/kill command channel

Dify 근거: `workflow_entry.py`, `persistence.py`, `observability.py`.

### P1. Workflow-as-Tool / Agent-as-Tool

Hermes skill 또는 saved workflow를 tool schema로 노출한다.

예:

- `run_saved_workflow(name, inputs)`
- `run_agent_harness(goal, tools, acceptance_tests)`
- `run_benchmark_case(repo, task, oracle)`

Dify 근거: `core/tools/workflow_as_tool/tool.py`.

### P1. Single-node / step replay harness

Agent Board에서 “이 tool call만 재실행”, “이 subagent만 다른 model로 재실행”, “이 artifact node부터 resume”을 지원한다.

Dify 근거: `single_iteration_generate`, `single_loop_generate`, `_prepare_single_node_execution()`.

### P1. VariablePool / selector 기반 artifact wiring

Hermes의 tool 결과와 subagent output을 문자열 transcript가 아니라 typed variable로 저장한다.

예:

- `@tool.terminal.stdout`
- `@subagent.review.findings[]`
- `@artifact.decision_log.items[]`
- `@run.coverage.percent`

Dify 근거: `VariablePool`, `variable_pool_initializer.py`, variable selector extraction.

### P2. Human input as pause state

`clarify`, terminal approval, credential missing, CAPTCHA/browser login 등을 run pause로 모델링한다. 현재의 단발 질문보다 UI에서 `paused_nodes`를 볼 수 있게 한다.

Dify 근거: `GraphRunPausedEvent`, `HumanInputRequired`, `human_input_*` modules.

### P2. Trigger nodes

Hermes cron/webhook/gateway message를 trigger node로 통합한다.

Dify 근거: `api/core/trigger`, `nodes/trigger_schedule`, `nodes/trigger_webhook`, `nodes/trigger_plugin`.

## 권장 구현 순서

1. `agent/run_events.py` 추가: Pydantic/dataclass event models.
2. `agent/run_graph.py` 추가: `RunGraph`, `RunNode`, `RunEdge`, `RunRuntimeState`.
3. `agent/run_layers.py` 추가: `RunLayer` protocol과 기본 레이어 3개(Persistence/Budget/Artifact).
4. `run_agent.py`에 최소 instrumentation: model call/tool call/subagent call을 event emit.
5. `tools/delegate_tool.py` active subagent registry를 run graph node로 연결.
6. Gateway/TUI/Agent Board가 `run_events` stream을 구독하도록 API 추가.
7. benchmark harness는 run graph를 평가 단위로 사용: node별 oracle, artifact snapshot, replay.

## 주의점

- Dify의 `graphon` 전체를 가져오는 것은 과하다. Hermes에는 이미 tool registry와 subagent runtime이 있으므로 “Dify의 계약과 레이어링”만 가져오는 편이 맞다.
- Hermes의 장점은 동적 toolset/플랫폼/gateway/terminal harness이므로, Dify처럼 app/workflow 제품 모델에 너무 강하게 결합하지 말고 `RunGraph`를 backend-neutral하게 유지해야 한다.
- 우선 UI를 위해 event schema를 안정화하고, 그래프 실행 엔진은 나중에 선택적으로 강화하는 접근이 안전하다.

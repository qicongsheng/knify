# knify

Development tools for python.

---

# scheduler — 轻量级任务调度器

`knify.scheduler` 是一个**单文件、纯内存**的 Python 任务调度器，聚焦解决"同一任务多实例重叠执行"导致的资源竞争与数据不一致问题。支持 Cron 调度、并发控制、阻塞策略、失败重试、超时控制与生命周期管理。

对应设计文档：`Python轻量级任务调度系统设计文档V2.md`。

## 特性

- **Cron 调度**：支持 5 位（`分 时 日 月 周`）与 6 位（`秒 分 时 日 月 周`）表达式，按字段数自动识别
- **并发控制**：`max_instances` 限制同一任务的并发实例数，默认 `1`
- **阻塞策略**：并发满时支持 `WAIT`（排队）/ `DROP`（丢弃）/ `RAISE`（抛异常）
- **失败重试**：可配置重试次数与间隔，重试非阻塞（不占用 worker 线程）
- **超时控制**：同步任务软超时、异步任务硬取消
- **同步 / 异步**：按函数类型自动路由，同步进线程池，`async def` 进事件循环
- **生命周期**：运行时添加、移除、暂停、恢复、更新参数、手动触发、清理队列
- **可观测**：结构化 JSON 日志 + 状态/统计查询

## 依赖

```bash
pip install croniter pytz
```

日志复用项目的 `knify.logger`（loguru 封装）。

## 快速开始

```python
from knify.scheduler import Scheduler

scheduler = Scheduler(
    timezone="Asia/Shanghai",
    max_workers=10,                 # 同步任务线程池大小
    default_max_instances=1,
    default_blocking_strategy="WAIT",
    default_blocking_timeout=300,
)

# 方式一：装饰器
@scheduler.task(task_id="data_sync", cron="0 */2 * * *",
                run_immediately=True, retry_times=3)
def sync_data():
    ...

# 方式二：链式
scheduler.add_job(
    task_id="cache_refresh",
    func=refresh_cache,
    cron="*/1 * * * *",
    blocking_strategy="DROP",
)

scheduler.start()                   # 阻塞主线程；start(block=False) 则后台运行
```

停止：

```python
scheduler.shutdown(wait=True, timeout=30)
```

## 任务参数

| 参数 | 类型 | 默认 | 说明 |
| :--- | :--- | :--- | :--- |
| `task_id` | `str` | 必填 | 全局唯一标识 |
| `func` | `Callable` | 必填 | 同步函数或 `async def` |
| `cron` | `str` | 必填 | 5 位或 6 位 Cron |
| `args` | `List` | `[]` | 位置参数 |
| `kwargs` | `Dict` | `{}` | 关键字参数 |
| `run_immediately` | `bool` | `False` | 注册后（`start()` 时）立即执行一次 |
| `max_instances` | `int` | `1` | 最大并发（逻辑槽位）实例数 |
| `blocking_strategy` | `str` | `"WAIT"` | `WAIT` / `DROP` / `RAISE` |
| `blocking_timeout` | `int` | `300` | WAIT 队列等待超时（秒） |
| `max_queue_size` | `int` | `100` | WAIT 队列最大长度 |
| `retry_times` | `int` | `0` | 失败（含超时）重试次数 |
| `retry_delay` | `int` | `60` | 重试间隔（秒），非阻塞延迟 |
| `timeout` | `int` | `None` | 单次执行超时（秒） |
| `name` | `str` | `None` | 可读名称（仅展示） |

## 阻塞策略

当新触发到来且 `running_count >= max_instances`：

| 策略 | 行为 |
| :--- | :--- |
| `WAIT` | 进 FIFO 队列（状态 `BLOCKED`），有槽位释放时按序唤醒；队列满或等待超过 `blocking_timeout` 则拒绝 |
| `DROP` | 直接拒绝（状态 `REJECTED`，记 WARNING） |
| `RAISE` | 抛 `MaxInstancesReachedError`——**仅对 `trigger_job` 手动触发有效**；Cron/immediate 自动触发遇 `RAISE` 会**降级为 DROP** 并记 WARNING |

## 实例状态

状态属于**实例**而非任务（一个任务可同时有多个实例）。任务只持聚合计数。

| 状态 | 含义 | 终态 |
| :--- | :--- | :--- |
| `BLOCKED` | 并发满，WAIT 队列等待 | 否 |
| `PENDING_RETRY` | 失败后等待重试 | 否 |
| `RUNNING` | 执行中（含线程池排队） | 否 |
| `SUCCESS` | 成功 | ✅ |
| `FAILED` | 失败且重试耗尽 | ✅ |
| `TIMEOUT` | 超时且重试耗尽 | ✅ |
| `CANCELLED` | 被移除/清理取消 | ✅ |
| `REJECTED` | 被 DROP/队列满/等待超时拒绝 | ✅ |

## 重试与超时语义

- **超时算失败**：超时纳入重试；重试耗尽后终态为 `TIMEOUT`（最后一次超时）或 `FAILED`（普通异常）。
- **重试非阻塞**：失败后释放 worker，按 `retry_delay` 延迟由主循环重新投递；**逻辑槽位在重试期间保持占用**（`running_count` 不减）。
- **同步软超时**：Python 线程无法强杀。到期后调度器停止等待、标记 `TIMEOUT`、释放逻辑槽位，但**后台线程可能仍在运行**（不保证回收）。若配置了重试，软超时后旧线程与新尝试可能短暂并存（at-least-once）。
- **异步硬取消**：`async def` 任务通过 `asyncio.wait_for` 在 `await` 点被真实取消。

## 管理 API

```python
scheduler.get_job_status("data_sync")
# {
#   "task_id", "name", "enabled",
#   "max_instances", "running_instances", "blocked_queue_size",
#   "next_run_time", "last_run_time", "last_status",
#   "success_count", "failed_count", "total_triggered",
#   "args", "kwargs", "blocking_strategy", "last_trigger_source"
# }

scheduler.update_job_params("data_sync", args=[...], kwargs={...})  # 仅影响后续触发
scheduler.trigger_job("data_sync")            # 手动触发一次
scheduler.pause_job("data_sync")              # 停止 Cron 触发
scheduler.resume_job("data_sync")             # 恢复 Cron 触发
scheduler.remove_job("data_sync")             # 移除；队列实例置 CANCELLED，运行中不强杀
scheduler.get_blocked_jobs()                  # {task_id: [instance_id, ...]}
scheduler.clear_blocked_queue("data_sync")    # 清空 WAIT 队列（置 CANCELLED）
```

> **参数快照**：实例在触发那一刻对 `args`/`kwargs` 做快照并持有至终结。`update_job_params()` 只影响此后新产生的触发，已在运行/排队/待重试的实例继续用各自快照。

## 日志

每条日志为 JSON，经 `knify.logger` 输出，字段包含 `timestamp`、`task_id`、`instance_id`、`event`、`source`、`attempt`、`args`、`kwargs`，完成事件带 `duration_ms`，失败事件带 `error`。

| 级别 | 事件 |
| :--- | :--- |
| INFO | `start` / `success` / `blocked` |
| WARNING | `rejected` / `retry` / 容量提示 / 停机超时 |
| ERROR | `failed` / `timeout` |

## 已知限制

- **无持久化**：纯内存，进程重启后任务与状态清空。
- **单进程**：不支持分布式；`max_workers` 是全局硬上限。若 `sum(max_instances) > max_workers`，同步任务会在线程池内部排队，`start()` 时会发容量 WARNING。
- **同步超时不可强杀**：见上文软超时说明。
- **信号**：Linux 监听 `SIGINT`/`SIGTERM`；Windows 仅 `SIGINT`（Ctrl+C）可靠，建议 Windows 下显式调用 `shutdown()`。

## 运行测试

```bash
pip install pytest croniter pytz
python -m pytest tests/test_scheduler.py -q
```

覆盖：Cron 校验（5/6 位）、WAIT/DROP/RAISE、并发准入、重试成功/失败、软超时、异步任务与硬取消、立即触发、参数快照、暂停/恢复、移除/清理队列、装饰器注册、统计计数等 29 个用例。

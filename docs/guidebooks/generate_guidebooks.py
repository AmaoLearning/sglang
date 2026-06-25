#!/usr/bin/env python3
"""Generate contributor-oriented SGLang guidebook notebooks.

The notebooks are intentionally source-aware: most code cells inspect the local
checkout instead of launching a model. This keeps them useful on laptops while
still teaching the real implementation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "guidebooks"


def _cell_id(kind: str, source: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"sglang-guidebooks:{kind}:{source}"))[:8]


def md(source: str) -> dict:
    source = source.strip() + "\n"
    return {
        "cell_type": "markdown",
        "id": _cell_id("markdown", source),
        "metadata": {},
        "source": source,
    }


def code(source: str) -> dict:
    source = source.strip() + "\n"
    return {
        "cell_type": "code",
        "id": _cell_id("code", source),
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source,
    }


CALL_EXPLANATIONS = {
    "Engine._launch_subprocesses": "启动并连接 SRT engine 的内部组件，返回 manager、IPC 端口、scheduler 初始化信息和 watchdog。",
    "_setup_and_run_http_server": "把已经启动的 engine 组件挂到 FastAPI app 上，并启动 HTTP server。",
    "set_global_state": "把 manager/template/scheduler 信息放入 HTTP 全局状态，endpoint 之后通过它拿到 runtime 对象。",
    "write_data_for_multi_tokenizer": "多 tokenizer worker 模式下通过共享内存传递启动参数。",
    "add_api_key_middleware": "把 API key/admin API key 鉴权逻辑注册到 FastAPI middleware。",
    "uvicorn.run": "启动默认 ASGI HTTP server，真正开始监听请求。",
    "_run_granian_server": "启动 Granian HTTP/2 server，是 HTTP/2 路径的替代 server backend。",
    "PortArgs.init_new": "分配 tokenizer/scheduler/detokenizer 之间 IPC 通信所需的端口或 socket 名称。",
    "load_plugins": "加载插件，让插件有机会注册模型、参数 hook 或 speculative/grammar 扩展。",
    "server_args.check_server_args": "在进程启动前做参数一致性校验，避免子进程启动后才失败。",
    "scheduler_init_result.wait_for_ready": "等待 scheduler/model worker 完成初始化并回传可服务状态。",
    "SubprocessWatchdog": "监控 scheduler/detokenizer 子进程存活，避免主进程静默挂着坏服务。",
    "TypeBasedDispatcher": "按返回对象类型分发处理函数，减少 tokenizer manager 中的 if/else 回包分支。",
    "self.init_communicators": "初始化 tokenizer manager 与 scheduler/detokenizer 间的 IPC 通道。",
    "obj.normalize_batch_and_arguments": "把单请求/批请求和参数别名规范化，后续路径才能统一处理。",
    "self._set_default_priority": "为请求补齐默认优先级，供 scheduler priority policy 使用。",
    "self._init_req_state": "创建 rid 到 ReqState 的映射，后续 streaming/non-streaming 回包都靠它找到等待者。",
    "self._tokenize_one_request": "把用户输入文本、多模态数据、chat template 处理成内部 tokenized request。",
    "self._send_one_request": "把 tokenized request 通过 IPC 发给 scheduler。",
    "self._wait_one_response": "等待 scheduler/detokenizer 回包，并按 streaming/non-streaming 产出 API 响应。",
    "self._handle_batch_output": "把 batch 输出拆回每个 rid，并整理 meta_info、文本、logprob、finish reason。",
    "get_zmq_socket": "创建 ZeroMQ socket，是 manager 进程之间传对象的底层通道。",
    "get_tokenizer": "加载 Hugging Face 或自定义 tokenizer，供 detokenization 或模板处理使用。",
    "key.page_aligned": "把 key 截到 page 边界，保证命中的 KV span 能被 page allocator 安全复用。",
    "self._match_prefix_helper": "沿 radix tree 递归寻找最长已缓存前缀。",
    "self._split_node": "当匹配在节点中间结束时拆节点，给未来请求留下精确边界。",
    "tree_cache.match_prefix": "查询 prefix cache，把可复用 KV slot 和节点锚点返回给 scheduler。",
    "zero_match_result": "把一次命中强制归零，常用于调试或禁用 radix 命中的实验。",
    "match_prefix_for_req": "把 cache 命中结果写回 Req，供排序和 KV 分配使用。",
    "ForwardBatch.init_new": "把 scheduler 的 CPU 侧 batch 状态转换为 model runner/attention backend 使用的 tensor 元数据。",
    "self.recv_requests": "从 tokenizer manager 接收新请求和控制消息。",
    "self.get_new_batch_prefill": "从 waiting queue 选择下一批可进入 prefill/extend 的请求。",
    "self.run_batch": "调用 model worker 执行当前 batch，并返回采样/forward 结果。",
    "self.process_batch_result": "把 forward/sampling 结果写回请求状态、发送输出并维护 cache。",
    "self.tp_worker.forward_batch_generation": "让 TP model worker 对 batch 执行生成 forward。",
    "self.grammar_backend.get_cached_or_future_value": "从 grammar cache 获取已编译对象；未命中则提交异步编译任务。",
    "self.grammar_backend.set_cache": "把编译成功或失败的 grammar 放回 cache，后续相同 schema 复用。",
    "torch.distributed.all_gather_object": "跨 rank 同步 grammar ready/failed 集合，保证各 rank batch 一致。",
    "GrammarMatcher": "xgrammar 的状态机 matcher，负责接受 token、回滚和生成下一步 bitmask。",
    "allocate_token_bitmask": "为 constrained decoding 分配 token 级合法性 bitmask。",
    "self.matcher.fill_next_token_bitmask": "把当前 grammar 状态下的合法 token 写入 bitmask。",
    "apply_token_bitmask_inplace_triton": "在 GPU logits 上原地应用 token mask，非法 token 会被屏蔽。",
    "self.matcher.find_jump_forward_string": "寻找当前 grammar 状态下可直接跳过的确定字符串片段。",
    "SpeculativeAlgorithm.from_string": "把 CLI/参数字符串解析成内建或插件 speculative algorithm 对象。",
    "_get_registered_spec": "查询插件注册的 speculative algorithm。",
    "self.factory": "调用插件提供的 worker factory，得到自定义 speculative worker 类。",
    "build_eagle_disagg_draft_input": "在 disaggregation 模式下构造 EAGLE draft 阶段所需输入。",
    "self.target_worker.forward_batch_generation": "用 target model 执行 verify 或普通生成 forward。",
    "self.draft_worker.draft_extend": "让 draft worker 基于 target hidden/last token 扩展候选。",
    "compute_dflash_correct_drafts_and_bonus": "计算 DFLASH greedy verify 下可接受 draft 数和 bonus token。",
    "self.cache_controller.write": "把 device KV 写入 host pool，作为 HiCache L2 备份。",
    "self.cache_controller.write_storage": "把 host KV 写到 L3 storage backend，供跨实例复用。",
    "self.cache_controller.prefetch": "发起从 L3 storage 到 host pool 的异步预取。",
    "self.cache_controller.terminate_prefetch": "结束预取并返回实际完成 token 数。",
    "self.evict_host": "从 host KV pool 中驱逐页面，为新的 load-back/prefetch 腾空间。",
    "logging.getLogger": "取得当前模块的 logger；日志名通常跟 `__name__` 绑定，便于按模块过滤。",
    "dataclasses.field": "为 dataclass 字段指定 default factory、metadata 或 init 行为。",
    "os.getenv": "读取环境变量开关；这类分支常用于调试、实验功能或部署差异。",
    "torch.empty": "预分配 tensor 存储，后续 kernel 或 copy 会填充真实内容。",
    "torch.zeros": "分配并清零 tensor，常用于 mask、计数器或初始化状态。",
    "torch.tensor": "把 Python/NumPy 数据转换成 Torch tensor，进入模型执行或通信路径。",
    "asyncio.create_task": "把协程放到事件循环后台执行，调用方不会同步等待它完成。",
    "copy.copy": "创建浅拷贝；对象内部可变成员仍可能共享，读状态生命周期时要留意。",
    "copy.deepcopy": "创建深拷贝；常用于每请求状态隔离，避免复用缓存对象时串状态。",
}


def _is_assignment(stripped: str) -> bool:
    if "=" not in stripped:
        return False
    if stripped[0] in ")]}":
        return False
    if stripped in {")", "]", "}", "):", "]:", "}:"} or stripped.startswith(
        ("f\"", "f'", "\"", "'")
    ):
        return False
    if stripped.startswith(("if ", "elif ", "while ", "for ", "return ", "assert ")):
        return False
    if stripped.startswith(("logger.", "raise ")):
        return False
    return not any(op in stripped for op in ("==", "!=", "<=", ">=", ":="))


def _comment_marker(line: str) -> str:
    return "//" if line.lstrip().startswith("//") else "#"


def _annotation_for_assignment(left: str, right: str) -> str:
    left = left.strip()
    right = right.strip()
    bare_left = left.split(":", 1)[0].strip()
    lower_left = bare_left.lower()
    lower_right = right.lower()

    if bare_left.startswith("self."):
        attr = bare_left.split(".", 1)[1]
        if "args" in lower_left:
            return f"成员变量写入：`{bare_left}` 保存启动/请求配置，后续方法会以它决定分支行为。"
        if "manager" in lower_left:
            return f"成员变量写入：`{bare_left}` 保存 manager 引用，是跨组件调用的入口。"
        if "queue" in lower_left:
            return f"成员变量写入：`{bare_left}` 保存队列状态，后续 event loop 会持续消费或填充它。"
        if "pool" in lower_left or "cache" in lower_left:
            return f"成员变量写入：`{bare_left}` 保存缓存/内存池资源，生命周期会跨越多个请求。"
        if "token" in lower_left or "ids" in lower_left:
            return f"成员变量写入：`{bare_left}` 保存 token 相关状态，后续长度计算、cache key 或采样都会读取它。"
        if "lock" in lower_left:
            return f"成员变量写入：`{bare_left}` 保存并发保护对象，避免请求处理和后台更新互相踩状态。"
        if "event" in lower_left:
            return f"成员变量写入：`{bare_left}` 保存同步事件，用来把后台结果通知等待中的请求路径。"
        return f"成员变量写入：`{bare_left}` 会留在对象生命周期中，后续方法可能依赖这份状态。"

    if bare_left.startswith(("app.", "req.", "state.", "node.", "server_args.")):
        owner = bare_left.split(".", 1)[0]
        return f"对象状态写入：`{bare_left}` 修改 `{owner}` 的可见状态，读源码时要继续追踪它在哪里被消费。"

    if lower_left in {"logger", "log"}:
        return "局部状态绑定：创建模块 logger，后续只负责日志输出，不改变请求执行语义。"
    if "args" in lower_left or "config" in lower_left:
        return f"局部状态绑定：`{bare_left}` 保存配置快照，下面的分支通常会基于它选择执行路径。"
    if ":" in left and not bare_left.startswith(("lambda", "for ")):
        return f"字段/变量声明：`{bare_left}` 带有类型信息；它描述这个对象或阶段会保存的状态形状。"
    if "socket" in lower_left or "port" in lower_left:
        return f"局部状态绑定：`{bare_left}` 保存通信端点，后续 manager 间 IPC 会使用它。"
    if "future" in lower_left or "task" in lower_left:
        return f"局部状态绑定：`{bare_left}` 保存异步任务句柄，后续会检查完成、取消或取结果。"
    if "mask" in lower_left or "bitmask" in lower_left:
        return f"局部状态绑定：`{bare_left}` 保存 mask 数据，后续会用于 logits 过滤或状态筛选。"
    if "indices" in lower_left or "loc" in lower_left:
        return f"局部状态绑定：`{bare_left}` 保存位置/索引映射，通常会连接请求逻辑 token 与 KV 物理槽位。"
    if "req" in lower_left or "batch" in lower_left:
        return f"局部状态绑定：`{bare_left}` 保存请求或 batch 状态，后续调度/执行会继续改写它。"
    if any(name in lower_right for name in CALL_EXPLANATIONS):
        return f"局部状态绑定：`{bare_left}` 接住关键调用结果，后续代码会基于它继续装配组件或推进请求。"
    return f"局部状态绑定：`{bare_left}` 保存本阶段的中间结果，后续几行通常会立即消费它。"


def _annotation_for_source_line(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith(('"""', "'''")):
        return None
    if stripped.startswith(("import ", "from ")):
        return None
    if stripped.startswith("logger = logging.getLogger"):
        return None
    if stripped.endswith(",") and not stripped.startswith("self."):
        # Usually a function signature argument or tuple/list item. Annotating
        # these as assignments is noisy; surrounding function/class blocks carry
        # the real meaning.
        return None
    if stripped.startswith("__slots__"):
        return "成员变量声明：`__slots__` 限定实例可保存的字段，读这个类时可先把这些字段当作对象状态地图。"
    if stripped.startswith("class "):
        name = stripped.split("(", 1)[0].replace("class", "", 1).strip().rstrip(":")
        return f"类定义：`{name}` 是这一段的状态/行为边界；先看字段，再看哪些方法会改字段。"
    if stripped.startswith(("def ", "async def ")):
        name = stripped.split("(", 1)[0].replace("async def", "").replace("def", "").strip()
        prefix = "异步函数定义" if stripped.startswith("async def ") else "函数定义"
        return f"{prefix}：`{name}` 是调用边界；参数决定它从上游接收哪些状态，返回值决定下游能看到什么。"
    if stripped.startswith("return "):
        return "返回出口：把本阶段整理出的状态交给调用方；读调用链时要回到上层看它如何被消费。"
    if stripped == "return":
        return "返回出口：提前结束当前路径，通常表示这个分支已经完成处理或无需继续推进。"
    if stripped.startswith("yield "):
        return "流式产出：把一个中间结果交给上游迭代器，函数状态会在下一次迭代时继续。"
    if stripped.startswith(("continue", "break")):
        return "循环控制：跳过或结束当前循环轮次，通常代表这个请求/节点已被当前分支处理完。"
    if stripped.startswith("if "):
        condition = stripped[3:].rstrip(":")
        if condition == "TYPE_CHECKING":
            return "类型检查分支：只给静态类型工具导入重依赖，运行时不会进入这条路径。"
        if condition == "(":
            return "多行分支开始：完整条件在接下来几行，通常用于组合多个请求参数或运行时状态。"
        if "server_args" in condition:
            return f"分支判断：根据启动参数 `{condition}` 选择服务拓扑、通信方式或功能开关。"
        if "sampling_params" in condition or "grammar" in condition:
            return f"分支判断：根据请求的采样/grammar 约束 `{condition}` 决定是否进入受限解码路径。"
        if "req" in condition or "batch" in condition:
            return f"分支判断：根据请求/batch 状态 `{condition}` 决定调度、执行或回包路径。"
        if "cache" in condition or "pool" in condition or "memory" in condition:
            return f"分支判断：根据缓存/内存资源 `{condition}` 决定是否复用、加载、驱逐或降级。"
        return f"分支判断：只有满足 `{condition}` 时才进入该路径；这通常是在区分部署模式、请求类型或资源状态。"
    if stripped.startswith("elif "):
        condition = stripped[5:].rstrip(":")
        if "server_args" in condition:
            return f"补充分支：前面的启动模式不匹配时，再按 `{condition}` 选择另一种服务拓扑。"
        if "cache" in condition or "pool" in condition:
            return f"补充分支：前面的缓存/资源条件不满足时，再检查 `{condition}` 对应的降级或替代路径。"
        return f"补充分支：前面的条件不满足时，再检查 `{condition}`。"
    if stripped.startswith("else:"):
        return "兜底分支：前面的 if/elif 都不成立时进入，常代表默认模式或降级路径。"
    if stripped.startswith("try:"):
        return "异常边界：下面的调用可能跨进程、I/O 或用户输入，失败时需要清理内部状态。"
    if stripped.startswith("except "):
        return "异常处理分支：把失败转换成可控清理、缓存失败对象或用户可见错误。"
    if stripped.startswith("for "):
        return "循环处理：通常是在遍历请求、rank、worker、token 或候选项。"
    if stripped.startswith("while "):
        return "循环等待/轮询：注意退出条件，否则容易造成 busy wait 或阻塞。"

    if re.match(r"^[A-Za-z_][\w\.]*\s*:\s*[^=]+$", stripped):
        name = stripped.split(":", 1)[0].strip()
        return f"字段/变量声明：`{name}` 带有类型信息；它描述这个对象或阶段会保存的状态形状。"

    if _is_assignment(stripped):
        left, right = stripped.split("=", 1)
        return _annotation_for_assignment(left, right)

    for name, explanation in CALL_EXPLANATIONS.items():
        if name in stripped:
            return f"关键调用：`{name}` - {explanation}"

    call_match = re.search(r"([A-Za-z_][\w\.]*?)\(", stripped)
    if call_match and not stripped.startswith(("def ", "class ")):
        name = call_match.group(1)
        if name in {"print", "len", "range", "isinstance", "getattr", "setattr", "list", "dict", "tuple", "set"}:
            return None
        if name.startswith("self."):
            return f"成员函数调用：`{name}` 会读取或更新当前对象状态，建议继续查看该方法定义。"
        if "." in name:
            return f"对象/库方法调用：`{name}` 把当前对象状态交给另一个组件处理，建议追踪该对象的生命周期。"
        return f"函数/库调用：`{name}` 把当前阶段委托给外部 helper 或库实现。"
    return None


def source_block(path: str, start: int, end: int, lang: str = "python") -> str:
    """Return a fenced source excerpt with line numbers.

    Keep excerpts short and purposeful. The surrounding prose should explain why
    the block matters instead of asking readers to infer it from raw code.
    """
    lines = (ROOT / path).read_text().splitlines()
    rendered = []
    for lineno in range(start, min(end, len(lines)) + 1):
        line = lines[lineno - 1]
        rendered.append(f"{lineno:4d}: {line}")
        annotation = _annotation_for_source_line(line)
        if annotation:
            marker = _comment_marker(line)
            rendered.append(f"      {marker} 注：{annotation}")
    excerpt = "\n".join(rendered)
    return f"```{lang}\n# {path}:{start}-{end}\n{excerpt}\n```"


def guide(title: str, path: str, start: int, end: int, notes: list[str]) -> dict:
    note_text = "\n".join(f"- {note}" for note in notes)
    return md(
        f"""
### {title}

{source_block(path, start, end)}

**读这段时抓住：**

{note_text}
"""
    )


def write_notebook(filename: str, title: str, cells: list[dict]) -> None:
    nb = {
        "cells": [
            md(
                f"""
# {title}

> 面向即将加入 SGLang 开源社区的开发者。建议从仓库根目录启动 Jupyter，
> 或者在 notebook 第一格运行路径检查。本文以本地源码为主，线上文档为索引。
> Markdown 中的源码摘录会插入 `# 注：...` 行内讲解；可执行代码 cell 则保持可运行。
"""
            )
        ]
        + cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (OUT / filename).write_text(json.dumps(nb, ensure_ascii=False, indent=2) + "\n")


COMMON_SETUP = code(
    r"""
from pathlib import Path
import ast, inspect, re, textwrap

def find_repo_root(start=None):
    p = Path(start or Path.cwd()).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / "python" / "sglang").exists() and (candidate / "docs").exists():
            return candidate
    raise RuntimeError("没有找到 SGLang 仓库根目录，请从仓库内启动 notebook。")

ROOT = find_repo_root()
print(ROOT)

def read_rel(path):
    return (ROOT / path).read_text()

def show_lines(path, start, end):
    lines = read_rel(path).splitlines()
    for i in range(start, min(end, len(lines)) + 1):
        print(f"{i:4d}: {lines[i-1]}")

def find_defs(path, names=None):
    tree = ast.parse(read_rel(path))
    rows = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if names is None or node.name in names:
                rows.append((node.lineno, type(node).__name__, node.name))
    return sorted(rows)
"""
)


def nb00():
    write_notebook(
        "00_reading_map.ipynb",
        "00. 阅读地图：从文档用户到 Runtime 贡献者",
        [
            md(
                """
## 本套指南解决什么问题

SGLang 官网文档非常适合“我该传什么参数、怎么启动服务”。但贡献者还需要另一张地图：

- 一个请求从 HTTP API 到 tokenizer、scheduler、model runner、detokenizer 的路径。
- 为什么 RadixAttention 不是一个普通 attention kernel，而是“prefix KV cache + paged attention + scheduler”的协同设计。
- Structured Outputs 里 JSON schema / regex / EBNF 如何变成每步采样前的 token mask，以及为什么文档中会提到 compressed FSM / jump-forward。
- Speculative decoding 如何把 draft、verify、accept/reject、KV 提交串起来。
- HiCache 如何把 RadixAttention 的 L1 GPU KV cache 扩展成 L1/L2/L3 分层缓存。
- 新增特性通常落在哪些扩展点：server args、scheduler、model runner、attention backend、memory pool、grammar backend、spec worker、storage backend。

这组 notebook 的目标不是替代 API 文档，而是把“文档中的 Feature 名词”连回“源码中的对象、状态和边界”。
"""
            ),
            COMMON_SETUP,
            md(
                """
## 推荐阅读顺序

1. `00_reading_map.ipynb`：总览与源码地图。
2. `01_runtime_request_path.ipynb`：请求路径和进程/manager 边界。
3. `02_radix_attention_prefix_cache.ipynb`：RadixAttention、RadixCache、prefix reuse。
4. `03_scheduler_memory_execution.ipynb`：scheduler 如何把请求变成 GPU forward batch。
5. `04_structured_outputs_fsm.ipynb`：grammar backend、token mask、jump-forward / compressed FSM。
6. `05_speculative_decoding.ipynb`：EAGLE、STANDALONE、NGRAM、DFLASH 的共同骨架。
7. `06_hicache_disaggregation_new_features.ipynb`：HiCache、PD/EPD disaggregation、新特性的集成模式。
8. `07_contributor_playbook.ipynb`：贡献者改代码的路线、测试入口和 PR 思维方式。
"""
            ),
            code(
                r"""
docs_index = read_rel("docs/index.rst")
sections = re.findall(r":caption:\s*(.+?)\n\n(.*?)(?=\n\.\. toctree::|\Z)", docs_index, flags=re.S)
for caption, body in sections:
    entries = [line.strip() for line in body.splitlines() if line.strip() and not line.strip().startswith(":")]
    print(f"\n[{caption}]")
    for entry in entries[:12]:
        print(" -", entry)
    if len(entries) > 12:
        print(f" - ... {len(entries)-12} more")
"""
            ),
            md(
                """
## 关键源码区域

贡献者最常接触的是 `python/sglang/srt`。其中 SRT 是 SGLang Runtime：

- `entrypoints/`：HTTP / OpenAI / Ollama / Engine API 入口。
- `managers/`：tokenizer、scheduler、detokenizer 及调度数据结构。
- `model_executor/`：model runner、ForwardBatch、CUDA graph runner、forward context。
- `layers/`：RadixAttention、MoE、quantization、attention backend glue。
- `mem_cache/`：KV memory pool、RadixCache、HiRadixCache、HiCache storage backend。
- `constrained/`：structured outputs 的 grammar backend。
- `speculative/`：speculative decoding 的 worker、输入结构和 accept/reject kernel。
- `disaggregation/`：prefill/decode/encoder disaggregation。
"""
            ),
            code(
                r"""
interesting_dirs = [
    "python/sglang/srt/entrypoints",
    "python/sglang/srt/managers",
    "python/sglang/srt/model_executor",
    "python/sglang/srt/layers",
    "python/sglang/srt/mem_cache",
    "python/sglang/srt/constrained",
    "python/sglang/srt/speculative",
    "python/sglang/srt/disaggregation",
]
for d in interesting_dirs:
    files = sorted((ROOT / d).glob("*.py"))
    print(f"{d}: {len(files)} top-level .py files")
    for f in files[:8]:
        print("  ", f.name)
"""
            ),
            md(
                """
## Feature 到源码的索引

下面这个小表是后续章节的“找路牌”。你可以把它当成 grep 前的心智模型。
"""
            ),
            code(
                r"""
feature_map = {
    "HTTP/OpenAI API": [
        "python/sglang/srt/entrypoints/http_server.py",
        "python/sglang/srt/entrypoints/openai/",
        "python/sglang/srt/managers/tokenizer_manager.py",
    ],
    "Scheduler / continuous batching": [
        "python/sglang/srt/managers/scheduler.py",
        "python/sglang/srt/managers/schedule_batch.py",
        "python/sglang/srt/managers/schedule_policy.py",
    ],
    "RadixAttention / prefix cache": [
        "python/sglang/srt/layers/radix_attention.py",
        "python/sglang/srt/mem_cache/radix_cache.py",
        "python/sglang/srt/mem_cache/base_prefix_cache.py",
    ],
    "Structured outputs / FSM": [
        "python/sglang/srt/constrained/base_grammar_backend.py",
        "python/sglang/srt/constrained/grammar_manager.py",
        "python/sglang/srt/constrained/xgrammar_backend.py",
        "python/sglang/srt/constrained/outlines_jump_forward.py",
    ],
    "Speculative decoding": [
        "python/sglang/srt/speculative/spec_info.py",
        "python/sglang/srt/speculative/eagle_worker_v2.py",
        "python/sglang/srt/speculative/ngram_worker.py",
    ],
    "HiCache": [
        "python/sglang/srt/mem_cache/hiradix_cache.py",
        "python/sglang/srt/managers/cache_controller.py",
        "python/sglang/srt/mem_cache/hicache_storage.py",
    ],
}
for k, paths in feature_map.items():
    print(f"\n{k}")
    for p in paths:
        print(" -", p)
"""
            ),
            md(
                """
## 读源码时的三个不变量

- **请求状态分层**：API 层看到字符串和 JSON；scheduler 层看到 `Req` / `ScheduleBatch`；model runner 层看到 GPU tensor 和 `ForwardBatch`。
- **KV cache 是核心资源**：吞吐并不只取决于 kernel，还取决于哪些 token 已经有 KV、哪些 KV 被锁住、哪些可以驱逐。
- **Feature 很少孤立存在**：例如 structured outputs 会影响 sampling，spec decoding 会影响 KV 分配，HiCache 会影响 prefix matching 和 prefill 调度。
"""
            ),
        ],
    )


def nb01():
    write_notebook(
        "01_runtime_request_path.ipynb",
        "01. Runtime 请求路径：HTTP 到 Scheduler 再回到用户",
        [
            COMMON_SETUP,
            md(
                """
## 入口层：`sglang serve` / `python -m sglang.launch_server`

启动入口会解析 `ServerArgs`，然后根据模式分流到 HTTP、gRPC、Ray、encoder-only 或 disaggregation server。默认 HTTP 模式进入 `sglang.srt.entrypoints.http_server.launch_server`。
"""
            ),
            code(
                r"""
for path in ["python/sglang/launch_server.py", "python/sglang/srt/entrypoints/http_server.py"]:
    print("\n==", path)
    for row in find_defs(path, names={"run_server", "launch_server", "generate_request"}):
        print(row)
"""
            ),
            code(
                r"""
show_lines("python/sglang/launch_server.py", 12, 45)
"""
            ),
            guide(
                "启动分流：`run_server` 只决定拓扑，不做推理",
                "python/sglang/launch_server.py",
                12,
                43,
                [
                    "`encoder_only`、`grpc_mode`、`use_ray` 是互斥的服务形态分支；默认路径才进入 HTTP server。",
                    "这里没有 tokenizer、scheduler、model runner 的细节，说明启动入口的职责是选择 runtime 拓扑。",
                    "以后排查“为什么我的参数没有进入默认 HTTP server”时，先看这段分流条件。",
                ],
            ),
            md(
                f"""
### 默认 HTTP 路径的核心：`http_server.launch_server`

`run_server` 只是把默认分支交给这里；真正把 HTTP server、TokenizerManager、Scheduler 子进程、
Detokenizer 子进程装配起来的是 `launch_server`。下面这段代码很短，但它是默认服务模式的总装入口。

```python
# python/sglang/srt/entrypoints/http_server.py:2455-2497
# 阶段 1：声明可替换的构造函数。测试、Ray/fork、私有部署可以替换这些函数。
def launch_server(
    server_args: ServerArgs,
    # 注：server_args 是整个服务的配置对象；后续 engine 子进程和 HTTP server 都共享这份配置。
    init_tokenizer_manager_func: Callable = init_tokenizer_manager,
    # 注：可替换 TokenizerManager 初始化函数，测试或私有 fork 可以在这里注入自定义 manager。
    run_scheduler_process_func: Callable = run_scheduler_process,
    # 注：可替换 Scheduler 子进程入口；调度器和模型加载都在这条路径里。
    run_detokenizer_process_func: Callable = run_detokenizer_process,
    # 注：可替换 Detokenizer 子进程入口；输出 token 到文本的转换由它负责。
    execute_warmup_func: Callable = _execute_server_warmup,
    # 注：warmup 在 HTTP server lifecycle 中执行，用于提前触发模型/图/缓存准备。
    launch_callback: Optional[Callable[[], None]] = None,
    # 注：服务完成启动后可调用的回调，常用于测试或嵌入式部署通知外部系统。
):
    \"\"\"
    Launch SRT (SGLang Runtime) Server.

    The SRT server consists of an HTTP server and an SRT engine.
    ...
    \"\"\"
    # 阶段 2：先启动 SRT engine 的内部组件。
    # TokenizerManager 在主进程；Scheduler/Detokenizer 通常在子进程。
    (
        tokenizer_manager,
        template_manager,
        port_args,
        scheduler_init_result,
        subprocess_watchdog,
    ) = Engine._launch_subprocesses(...)
    # 注：返回的 tokenizer_manager 留在主进程；scheduler_init_result 携带 scheduler 回传的能力信息。

    # 阶段 3：再把 FastAPI/uvicorn 绑定到这些组件上，开始接 HTTP 请求。
    _setup_and_run_http_server(
        server_args,
        # 注：HTTP endpoint 会通过 global state 间接调用 tokenizer_manager。
        tokenizer_manager,
        template_manager,
        port_args,
        scheduler_init_result.scheduler_infos,
        # 注：scheduler_infos 让 HTTP/tokenizer 侧知道 max input length、model info 等运行时事实。
        subprocess_watchdog,
        execute_warmup_func=execute_warmup_func,
        launch_callback=launch_callback,
    )
```

**读这段时抓住：**

- `launch_server` 是默认 HTTP 服务的“装配函数”，不是请求处理函数。
- 它先启动 engine 子系统，再启动 HTTP server；这保证 API 开始监听前 scheduler/model 已经在加载或就绪流程中。
- 函数参数都是可注入的 callable，这也是测试和私有 fork 可以替换启动行为的原因。
- `scheduler_init_result.scheduler_infos` 会被传给 HTTP 层，后续 API 层才能知道 max input length 等 scheduler 能力。
"""
            ),
            guide(
                "`Engine._launch_subprocesses` 上半段：准备环境、端口和 Scheduler",
                "python/sglang/srt/entrypoints/engine.py",
                751,
                844,
                [
                    "`configure_logger`、`_set_envs_and_config`、`server_args.check_server_args()` 是进程启动前的全局准备。",
                    "`PortArgs.init_new` 分配 manager 间 IPC 地址；后面的 Tokenizer/Scheduler/Detokenizer 都靠它通信。",
                    "`_launch_scheduler_processes` 先启动 scheduler，因为模型加载和 scheduler 能力信息都来自那里。",
                    "多节点非 0 rank 可能只跑 scheduler/worker，不跑 tokenizer/detokenizer；这解释了为什么 HTTP API 通常只在 rank0 暴露。",
                ],
            ),
            guide(
                "`Engine._launch_subprocesses` 下半段：Detokenizer、TokenizerManager、ready 信号和 watchdog",
                "python/sglang/srt/entrypoints/engine.py",
                845,
                891,
                [
                    "detokenizer 子进程先启动，然后主进程初始化 TokenizerManager 或 MultiTokenizerRouter。",
                    "`scheduler_init_result.wait_for_ready()` 是关键同步点：HTTP 层不能盲目认为模型已经可用。",
                    "`max_req_input_len` 从 scheduler 回写给 tokenizer manager，输入长度校验才有真实模型/部署上下文。",
                    "`SubprocessWatchdog` 把 scheduler/detokenizer 崩溃变成主进程可感知事件，是生产服务韧性的一部分。",
                ],
            ),
            guide(
                "`_setup_and_run_http_server`：把 engine 状态挂到 FastAPI app 上",
                "python/sglang/srt/entrypoints/http_server.py",
                2251,
                2335,
                [
                    "`set_global_state` 把 tokenizer_manager/template_manager/scheduler_info 暴露给 FastAPI endpoint 依赖函数。",
                    "single-tokenizer 模式直接把 `server_args` 和 warmup kwargs 挂到 `app`；multi-tokenizer 模式则写共享内存给 worker 读。",
                    "API key middleware 只在 single-tokenizer 模式直接添加；多 tokenizer/多 worker 的 HTTP 启动路径不同。",
                    "最后根据 HTTP/2、SSL refresh、tokenizer worker 数选择 Granian 或 uvicorn 的不同启动方式。",
                ],
            ),
            md(
                """
## Manager 边界

SGLang 的默认 HTTP 服务不是一个“大函数直接 forward”。它把工作拆成几类 manager：

- `TokenizerManager`：API 请求、chat template、多模态预处理、tokenization、streaming 状态。
- `Scheduler`：waiting/running queue、prefix cache、KV pool、grammar queue、batch formation、forward 调用。
- `DetokenizerManager`：把 token ids 增量转回文本，并负责流式输出中的 offset 管理。
- `TpModelWorker` / `ModelRunner`：真正持有模型权重、attention backend、CUDA graph runner 和 KV cache pool。

这条边界非常重要：多数 Feature 要么在 tokenizer 层增加请求字段，要么在 scheduler 层改变调度/缓存，要么在 model runner/attention backend 层改变 tensor 执行。
"""
            ),
            guide(
                "`TokenizerManager.__init__` 的尾部：通信、dispatcher、采样参数类",
                "python/sglang/srt/managers/tokenizer_manager.py",
                545,
                575,
                [
                    "`TypeBasedDispatcher` 让 tokenizer manager 能处理 scheduler/detokenizer 返回的多种对象，而不是写一串 endpoint 专用回调。",
                    "`init_communicators` 建立 ZeroMQ/IPC 通道；这就是 API 进程和 scheduler/detokenizer 进程之间的边界。",
                    "`sampling_params_class = SamplingParams` 意味着请求参数在进入 scheduler 前已经被规范化成内部采样对象。",
                ],
            ),
            guide(
                "`DetokenizerManager.__init__`：它不是附属函数，而是独立进程角色",
                "python/sglang/srt/managers/detokenizer_manager.py",
                89,
                133,
                [
                    "detokenizer 只从 scheduler 收 token id / batch output，再把文本结果发回 tokenizer manager。",
                    "`skip_tokenizer_init` 会让它不加载 tokenizer；embedding/token-id-only 等路径可以绕开普通文本 detokenization。",
                    "这个边界减少 scheduler 的 CPU 文本处理负担，也让 streaming 输出可以和 GPU 调度解耦。",
                ],
            ),
            code(
                r"""
paths = [
    "python/sglang/srt/entrypoints/engine.py",
    "python/sglang/srt/managers/tokenizer_manager.py",
    "python/sglang/srt/managers/scheduler.py",
    "python/sglang/srt/managers/detokenizer_manager.py",
]
for path in paths:
    print("\n==", path)
    for lineno, kind, name in find_defs(path):
        if name in {
            "init_tokenizer_manager", "run_scheduler_process", "run_detokenizer_process",
            "TokenizerManager", "generate_request", "Scheduler",
            "event_loop_normal", "event_loop_overlap", "run_batch", "process_batch_result",
            "DetokenizerManager",
        }:
            print(f"{lineno:4d} {kind:18s} {name}")
"""
            ),
            md(
                """
## 请求对象的生命周期

粗略流程：

1. FastAPI endpoint 接收 `/generate` 或 `/v1/chat/completions`。
2. OpenAI serving 层把 chat/completion 请求转为内部 `GenerateReqInput`。
3. `TokenizerManager.generate_request` 负责 tokenization、多模态输入处理、采样参数校验，并把 tokenized 请求发给 scheduler。
4. `Scheduler` 把请求放入 waiting queue；grammar 请求可能先进 `GrammarManager` 队列等编译完成。
5. `get_new_batch_prefill` 根据调度策略、KV 可用量、prefix hit、chunked prefill 等形成 `ScheduleBatch`。
6. `ForwardBatch.init_new` 将 CPU 侧调度数据变成 GPU 侧 tensor 元数据。
7. `ModelRunner.forward` 执行模型，attention 层通过 `RadixAttention` 转给当前 attention backend。
8. scheduler 处理 logits/sampling/finish reason，把结果发往 detokenizer/tokenizer manager。
9. API 层按 non-streaming 或 streaming 返回。
"""
            ),
            guide(
                "`TokenizerManager.generate_request`：入站请求的主脊柱",
                "python/sglang/srt/managers/tokenizer_manager.py",
                576,
                632,
                [
                    "`auto_create_handle_loop()` 确保后台回包循环已经启动，否则请求发出去后没人消费 scheduler/detokenizer 输出。",
                    "`normalize_batch_and_arguments()` 把单请求/批请求、多种参数别名规范化，这是后续代码能统一处理的前提。",
                    "`model_update_lock.reader_lock` 保护权重/LoRA 更新期间的请求一致性；请求路径并不只处理文本。",
                    "单请求路径是 tokenize -> `_send_one_request` -> `_wait_one_response`；批请求走 `_handle_batch_request`，但仍会拆成内部 request state。",
                    "异常分支会清理 `rid_to_state`，这是防止早期校验失败导致内存状态泄漏的关键。",
                ],
            ),
            guide(
                "`TokenizerManager.handle_loop`：为什么响应能回到原请求",
                "python/sglang/srt/managers/tokenizer_manager.py",
                1824,
                1888,
                [
                    "它一直从 detokenizer/socket 读对象；Batch output 走 `_handle_batch_output`，控制类对象交给 dispatcher。",
                    "`rid_to_state` 是回包路由表：scheduler 只知道 request id，API 层等待的是对应 state 的 event/output list。",
                    "`meta_info` 在这里组装，所以许多用户可见统计信息并不是 model runner 直接返回的。",
                    "streaming 的增量 offset、logprob 文本化、finish reason 都在这一层被整理成 API 输出。",
                ],
            ),
            code(
                r"""
for path, names in [
    ("python/sglang/srt/managers/tokenizer_manager.py", {"generate_request", "_tokenize_one_request"}),
    ("python/sglang/srt/managers/scheduler.py", {"get_new_batch_prefill", "run_batch", "process_batch_result"}),
    ("python/sglang/srt/managers/schedule_batch.py", {"ScheduleBatch", "ForwardMode", "Req"}),
]:
    print("\n==", path)
    for row in find_defs(path, names=names):
        print(row)
"""
            ),
            guide(
                "`engine.py` 初始化边界：manager 进程在这里被拼起来",
                "python/sglang/srt/entrypoints/engine.py",
                117,
                175,
                [
                    "`SchedulerInitResult` 是 scheduler 初始化后回传给 HTTP/tokenizer 侧的能力摘要，例如 max input length、model info。",
                    "`init_tokenizer_manager` 不是单纯构造 tokenizer，它会启动 scheduler/detokenizer 进程并建立 IPC 名称。",
                    "如果一个 Feature 需要跨 manager 传递新字段，通常要顺着这里确认哪个进程先知道它。",
                ],
            ),
            md(
                """
## 读 `Scheduler` 时不要迷路

`scheduler.py` 很长，因为它同时处理普通 decode、overlap schedule、grammar、speculative decoding、disaggregation、LoRA、profiling、metrics、weight update 等路径。建议按这几个函数读：

- `__init__`：所有子系统如何挂到 scheduler 上。
- `event_loop_normal` / `event_loop_overlap`：主循环形状。
- `get_new_batch_prefill`：prefill batch 进入 GPU 的入口。
- `run_batch`：从 `ScheduleBatch` 到 model worker forward。
- `process_batch_result`：采样、finish、streaming、cache 更新。
"""
            ),
            guide(
                "`Scheduler.event_loop_normal`：普通调度主循环的形状",
                "python/sglang/srt/managers/scheduler.py",
                1506,
                1535,
                [
                    "循环每轮先 `recv_requests`，再处理 grammar-ready、running batch、new prefill batch 等状态。",
                    "`forward_ct` 和 watchdog 让 scheduler 可以暴露健康状态；调度循环本身也是生产系统对象。",
                    "普通循环和 overlap 循环分开，是因为 overlap schedule 要把 CPU 调度和 GPU forward 的依赖拆得更细。",
                ],
            ),
            guide(
                "`Scheduler.event_loop_overlap`：重叠调度不是简单开线程",
                "python/sglang/srt/managers/scheduler.py",
                1536,
                1565,
                [
                    "overlap 路径有专门的 `result_queue`，上一轮 GPU 结果可能在下一轮 CPU 调度时才回收。",
                    "许多 Feature 要分别验证 normal/overlap 两条路径，例如 speculative、grammar、abort、pause generation。",
                    "读 scheduler bug 时，要先确认当前服务是否启用了 overlap，否则你可能在读错主循环。",
                ],
            ),
            code(
                r"""
show_lines("python/sglang/srt/managers/scheduler.py", 1500, 1565)
"""
            ),
            md(
                """
## 小练习：定位一次 `/generate` 的关键函数

下面的 cell 不启动服务，只用 AST 找出关键定义。读源码时可以把这些行号作为入口点。
"""
            ),
            code(
                r"""
targets = {
    "python/sglang/srt/entrypoints/http_server.py": {"generate_request", "launch_server"},
    "python/sglang/srt/managers/tokenizer_manager.py": {"generate_request"},
    "python/sglang/srt/managers/scheduler.py": {"get_new_batch_prefill", "run_batch", "process_batch_result"},
}
for path, names in targets.items():
    print("\n" + path)
    for lineno, kind, name in find_defs(path, names):
        print(f"  {name}: line {lineno}")
"""
            ),
        ],
    )


def nb02():
    write_notebook(
        "02_radix_attention_prefix_cache.ipynb",
        "02. RadixAttention 与 Prefix KV Cache",
        [
            COMMON_SETUP,
            md(
                """
## 先纠正一个常见误解

`RadixAttention` 这个名字容易让人以为它只是一个 attention kernel。实际上它是一个跨层设计：

- `RadixAttention` layer 是模型中的 attention 抽象，负责把 Q/K/V 与 `ForwardBatch` 交给当前 attention backend。
- `RadixCache` / `HiRadixCache` 是 prefix KV cache 的 metadata tree，负责匹配、插入、拆分、锁定、驱逐。
- `SchedulePolicy` 会利用 prefix hit 长度调整 waiting queue 的优先级。
- KV memory pool 负责把 logical token span 映射到实际 KV slot。

RadixAttention 的收益来自“相同前缀不重新 prefill”，而不是仅仅来自某个单独 kernel。
"""
            ),
            code(
                r"""
for path in [
    "python/sglang/srt/layers/radix_attention.py",
    "python/sglang/srt/mem_cache/radix_cache.py",
    "python/sglang/srt/managers/schedule_policy.py",
]:
    print("\n==", path)
    for row in find_defs(path, names={"RadixAttention", "RadixCache", "RadixKey", "TreeNode", "match_prefix_for_req", "SchedulePolicy"}):
        print(row)
"""
            ),
            md(
                """
## `RadixKey`：prefix matching 的基本单位

`RadixKey` 包装 token ids，同时带 `extra_key`。`extra_key` 很关键：同样 token 序列在不同 LoRA、cache salt、某些隔离策略下不能混用 KV。

它还支持 bigram view，这是 EAGLE 这类 speculative decoding 与 prefix cache 交互时会用到的特殊视图。
"""
            ),
            guide(
                "`RadixKey` 的字段：token 序列之外还要带隔离维度",
                "python/sglang/srt/mem_cache/radix_cache.py",
                35,
                75,
                [
                    "`token_ids` 是 radix tree 的路径内容，但 `extra_key` 才决定这段 KV 能不能跨请求复用。",
                    "`is_bigram` 让同一份 token array 可以被解释为 bigram 序列，避免为 EAGLE 等路径额外 materialize tuple list。",
                    "`limit` 是 O(1) 视图上限，用来避免为了截断前缀而复制长 token 序列。",
                ],
            ),
            guide(
                "`RadixKey.match`：长公共前缀用 galloping search 避免 Python 逐 token 扫",
                "python/sglang/srt/mem_cache/radix_cache.py",
                120,
                160,
                [
                    "先检查 `extra_key`，这是 cache correctness 的第一道闸。",
                    "指数窗口 + 二分定位第一个分叉点，优化的是长 shared prefix 场景，这正是 prefix cache 的热点。",
                    "`page_size` 对齐在这里完成；后续返回的 KV indices 才能安全对应 page allocator。",
                ],
            ),
            code(
                r"""
from array import array
from sglang.srt.mem_cache.radix_cache import RadixKey

a = RadixKey(array("q", [1, 2, 3, 4, 5]), extra_key="tenant-a")
b = RadixKey(array("q", [1, 2, 3, 9]), extra_key="tenant-a")
c = RadixKey(array("q", [1, 2, 3, 4]), extra_key="tenant-b")

print("a vs b match:", a.match(b))
try:
    print(a.match(c))
except ValueError as e:
    print("extra_key isolation:", e)

bigram = RadixKey(array("q", [10, 11, 12, 13]), is_bigram=True)
print("bigram logical units:", list(bigram))
print("bigram len:", len(bigram))
"""
            ),
            md(
                """
## `RadixCache` 的核心操作

需要抓住四个操作：

- `match_prefix`：沿 radix tree 找最长已缓存前缀，返回 device indices、last node、host hit 等信息。
- `insert`：把完成 prefill/decode 的 KV span 插入 tree；必要时拆分节点。
- `inc_lock_ref` / `dec_lock_ref`：保护正在被请求使用的节点，避免被驱逐。
- `evict`：按策略回收未锁定叶子节点，释放 KV slots。
"""
            ),
            code(
                r"""
for name in ["match_prefix", "insert", "cache_finished_req", "cache_unfinished_req", "evict", "inc_lock_ref", "dec_lock_ref", "_split_node"]:
    rows = find_defs("python/sglang/srt/mem_cache/radix_cache.py", {name})
    print(rows[0] if rows else "missing", name)
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/mem_cache/radix_cache.py", 360, 455)
"""
            ),
            guide(
                "`RadixCache.match_prefix`：返回的不只是长度，而是一组调度/加载锚点",
                "python/sglang/srt/mem_cache/radix_cache.py",
                360,
                418,
                [
                    "`key.page_aligned` 说明 cache hit 的最小合法单位受 page size 约束。",
                    "`value` 是已命中的 device KV slot indices；scheduler 后续会把它放进 `req.prefix_indices`。",
                    "`last_device_node` / `last_host_node` / `best_match_node` 在普通 RadixCache 中基本相同，但 HiCache 会让它们分出 L1/L2/L3 语义。",
                ],
            ),
            guide(
                "`RadixCache.insert` 与 `cache_finished_req`：什么时候把请求写入 prefix tree",
                "python/sglang/srt/mem_cache/radix_cache.py",
                420,
                472,
                [
                    "`insert` 返回已有 prefix 长度和总长度，调用者据此知道新增了多少 cache metadata。",
                    "`cache_finished_req` 使用 `origin_input_ids + output_ids[:-1]`，最后一个 token 通常还没有可作为未来 prefix 的完整 KV 后继语义。",
                    "`kv_indices` 来自 req-to-token pool 的逻辑位置到 KV slot 映射，这里把请求生命周期内的 KV 提升为可复用 cache。",
                ],
            ),
            md(
                """
## Scheduler 如何“感知 cache”

`SchedulePolicy` 中的 LPM 表示 longest prefix match。等待队列里的请求会先计算 prefix hit，再按更可能复用 KV 的顺序进入 prefill。这就是为什么 prefix cache 不是被动缓存：调度器会主动把“能复用”的请求排到更合适的位置。
"""
            ),
            guide(
                "`match_prefix_for_req`：scheduler 把 cache hit 写回 Req",
                "python/sglang/srt/managers/schedule_policy.py",
                65,
                111,
                [
                    "这段是 RadixCache 和 Scheduler 的接缝：cache 返回 `MatchResult`，函数把它展开到 `Req` 字段。",
                    "`num_matched_prefix_tokens` 把 device hit 和 host hit 合并成调度视角的 prefix hit。",
                    "`SGLANG_RADIX_FORCE_MISS` 是调试开关，可以强制关闭命中以比较性能/正确性。",
                ],
            ),
            guide(
                "`SchedulePolicy.calc_priority`：prefix cache 会反过来影响谁先 prefill",
                "python/sglang/srt/managers/schedule_policy.py",
                145,
                214,
                [
                    "cache-aware policy 会先计算 prefix matches，再按 LPM 或 DFS weight 排序。",
                    "队列过长时 LPM 会退化到 FCFS，避免调度成本压过收益。",
                    "即使是 cache-agnostic policy，只要 radix 支持 fast match，也可能预先填充 prefix 信息供后续 load snapshot 使用。",
                ],
            ),
            code(
                r"""
show_lines("python/sglang/srt/managers/schedule_policy.py", 65, 130)
show_lines("python/sglang/srt/managers/schedule_policy.py", 170, 235)
"""
            ),
            md(
                """
## `RadixAttention.forward`：模型层与 backend 的交界

模型文件中普遍会实例化 `RadixAttention`，但真正的 attention 实现由 `get_attn_backend().forward(...)` 决定。这样同一个模型层可以挂 FlashInfer、Triton、FA3、TRT-LLM、MLA 等 backend。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/layers/radix_attention.py", 75, 135)
"""
            ),
            md(
                """
## 小测试：page 对 prefix matching 的影响

KV cache 经常按 page 管理。`RadixKey.match(..., page_size=N)` 会把匹配长度向下对齐到 page 边界。这样能保证返回的 KV span 对底层 page allocator 是合法的。
"""
            ),
            code(
                r"""
x = RadixKey(array("q", [1, 2, 3, 4, 5, 6]))
y = RadixKey(array("q", [1, 2, 3, 4, 9, 9]))
for page in [1, 2, 4]:
    print("page_size", page, "matched", x.match(y, page_size=page))
"""
            ),
            md(
                """
## 贡献者注意点

- 任何改变 prefix key 语义的 Feature，都要考虑 `extra_key`，否则可能跨租户/跨 LoRA 复用错误 KV。
- 任何改变 KV slot 生命周期的 Feature，都要检查 lock/ref、evict、cache_finished_req/cache_unfinished_req。
- 任何引入 page 粒度的 Feature，都要检查 `page_size > 1` 下是否仍然对齐。
"""
            ),
        ],
    )


def nb03():
    write_notebook(
        "03_scheduler_memory_execution.ipynb",
        "03. Scheduler、KV Memory Pool 与执行路径",
        [
            COMMON_SETUP,
            md(
                """
## Scheduler 关心的不是“一个请求”，而是“资源可行的下一批请求”

每轮循环里 scheduler 都要在这些约束之间取平衡：

- waiting queue 中哪些请求可以进入 prefill。
- running batch 中哪些请求继续 decode。
- KV cache 还有多少空位，可以驱逐多少，哪些节点被锁住。
- grammar 是否已编译完成。
- speculative decoding 是否需要 draft/verify。
- overlap schedule 是否允许 CPU 调度和 GPU 执行重叠。

这就是 SGLang 的吞吐核心：连续 batching、prefix cache、paged KV、chunked prefill 都在 scheduler 汇合。
"""
            ),
            code(
                r"""
for path in [
    "python/sglang/srt/managers/scheduler.py",
    "python/sglang/srt/managers/schedule_batch.py",
    "python/sglang/srt/mem_cache/memory_pool.py",
    "python/sglang/srt/model_executor/forward_batch_info.py",
    "python/sglang/srt/model_executor/model_runner.py",
]:
    print("\n==", path)
    for row in find_defs(path, names={"Scheduler", "Req", "ScheduleBatch", "ReqToTokenPool", "ForwardBatch", "ModelRunner"}):
        print(row)
"""
            ),
            md(
                """
## `Req`、`ScheduleBatch`、`ForwardBatch`

三个对象对应三个抽象层：

- `Req`：单个请求的 CPU 状态，包含 input ids、output ids、sampling params、prefix hit、grammar、finish reason。
- `ScheduleBatch`：scheduler 选出的一个 batch，仍以 Python/CPU 状态为主，但已经决定了 extend/decode、KV 分配等。
- `ForwardBatch`：model runner 消费的 tensor 化执行元数据，attention backend 依赖它知道 seq_lens、cache loc、forward mode。
"""
            ),
            guide(
                "`Req.__init__`：单个请求的“账本”",
                "python/sglang/srt/managers/schedule_batch.py",
                666,
                745,
                [
                    "`origin_input_ids` 是 prompt，`output_ids` 是 append-only 的生成结果；许多后续长度计算假设 output 只追加不重写。",
                    "`kv_committed_len` / `kv_allocated_len` 区分已经提交给请求语义的 KV 和临时/预分配 KV。",
                    "`extra_key`、`lora_id`、`routing_key` 等字段决定调度、cache 隔离和分布式路由，不只是 API 元数据。",
                ],
            ),
            guide(
                "`ScheduleBatch`：scheduler 侧 batch 同时拿着资源和请求",
                "python/sglang/srt/managers/schedule_batch.py",
                1671,
                1738,
                [
                    "`reqs` 是高层请求列表；`req_to_token_pool`、`token_to_kv_pool_allocator`、`tree_cache` 是共享资源引用。",
                    "batch-variant 字段记录 chunked prefill、split prefill、HiCache consumer index、metrics 等调度状态。",
                    "`input_ids`、`req_pool_indices` 等 tensor 字段是跨到 `ForwardBatch` 的桥，不是简单 Python list。",
                ],
            ),
            guide(
                "`ForwardBatch`：attention backend 真正读取的执行快照",
                "python/sglang/srt/model_executor/forward_batch_info.py",
                322,
                388,
                [
                    "`forward_mode`、`seq_lens`、`out_cache_loc` 是 attention backend 决定 prefill/decode/verify 行为的核心。",
                    "许多字段从 `ScheduleBatch` 借用而非复制，说明 stream isolation 和生命周期管理非常敏感。",
                    "speculative、DP attention、Mamba、encoder-decoder 都在这里挂执行元数据，所以新增执行路径往往会扩展 ForwardBatch。",
                ],
            ),
            code(
                r"""
for name in ["Req", "ScheduleBatch"]:
    rows = find_defs("python/sglang/srt/managers/schedule_batch.py", {name})
    print(name, rows)
for name in ["ForwardBatch", "ForwardMode"]:
    rows = find_defs("python/sglang/srt/model_executor/forward_batch_info.py", {name})
    print(name, rows)
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/managers/schedule_batch.py", 1, 35)
show_lines("python/sglang/srt/managers/schedule_batch.py", 35, 75)
"""
            ),
            md(
                """
## KV memory pool：为什么需要两层映射

LLM serving 中 KV cache 是巨大的 `[layers, tokens, heads, dim]` 存储。SGLang 会把请求逻辑位置映射到物理 KV slot：

- `ReqToTokenPool`：请求维度的 token position -> KV slot index。
- `TokenToKVPool` / allocator：KV slot index -> 每层 K/V tensor 中的实际位置。

这样 decode 时新增 token 只需追加 slot，prefix cache 命中时可以直接复用已有 slot indices。
"""
            ),
            code(
                r"""
for path in [
    "python/sglang/srt/mem_cache/memory_pool.py",
    "python/sglang/srt/mem_cache/allocator/base.py",
    "python/sglang/srt/mem_cache/common.py",
]:
    print("\n==", path)
    for lineno, kind, name in find_defs(path):
        if "Pool" in name or name in {"alloc_for_extend", "alloc_for_decode", "release_kv_cache", "evict_from_tree_cache"}:
            print(f"{lineno:4d} {kind:16s} {name}")
"""
            ),
            md(
                """
## prefill 与 decode 的调度差异

- **Prefill / extend**：一次处理 prompt 或 chunk，可能写入大量 KV；受 `max_prefill_tokens`、chunked prefill、prefix hit、grammar readiness 影响。
- **Decode**：每个 running request 通常前进一步；关注 `max_running_requests`、KV reserve、sampling、finish。

Speculative decoding 会把 decode 变复杂：一次可能 draft 多个 token，再由 target verify 接受若干 token。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/managers/scheduler.py", 2735, 2795)
show_lines("python/sglang/srt/managers/scheduler.py", 3178, 3225)
"""
            ),
            guide(
                "`get_new_batch_prefill`：新请求进入 GPU 前的门禁",
                "python/sglang/srt/managers/scheduler.py",
                2735,
                2795,
                [
                    "它不是简单 pop waiting queue，而要同时检查 grammar、memory、chunked prefill、disaggregation、priority 等条件。",
                    "这里形成的是 prefill/extend batch；decode 的 running batch 在另一条路径继续推进。",
                    "如果你新增调度策略，通常要看它在这段之前还是之后改变 waiting queue。",
                ],
            ),
            guide(
                "`run_batch`：scheduler 和 model worker 的窄腰",
                "python/sglang/srt/managers/scheduler.py",
                3178,
                3238,
                [
                    "`run_batch` 接收 `ScheduleBatch`，根据模式走普通 forward、speculative forward、embedding/score 等路径。",
                    "它是 GPU 执行的调用点，但仍在 scheduler 进程里负责前后状态 bookkeeping。",
                    "很多性能 Feature 会在这里附近插入计时、profile、overlap 或特殊 forward mode。",
                ],
            ),
            md(
                """
## ModelRunner：从 batch 到模型 forward

`ModelRunner` 是权重、attention backend、CUDA graph runner、forward context 的聚合点。新增模型时通常在 `srt/models` 实现模型结构；新增执行优化时通常会碰 `model_executor` 或 attention backend。
"""
            ),
            code(
                r"""
for name in ["ModelRunner", "forward", "forward_decode", "forward_extend"]:
    rows = find_defs("python/sglang/srt/model_executor/model_runner.py", {name})
    print(name, rows[:5])
"""
            ),
            md(
                """
## 小练习：用源码检查 Scheduler 主循环有哪些旁路 Feature

这个 cell 抓取 `Scheduler.__init__` 附近常见子系统名。它不是完整解析器，但能帮助你建立“Feature 都挂在哪里”的直觉。
"""
            ),
            code(
                r"""
scheduler_src = read_rel("python/sglang/srt/managers/scheduler.py")
keywords = [
    "grammar", "spec", "lora", "disaggregation", "hicache",
    "overlap", "cuda_graph", "metrics", "profile", "cache_controller",
]
for kw in keywords:
    hits = [i+1 for i, line in enumerate(scheduler_src.splitlines()) if kw in line.lower()]
    print(f"{kw:18s}", hits[:10], "..." if len(hits) > 10 else "")
"""
            ),
            md(
                """
## 贡献者注意点

- Scheduler 里的 bug 往往是状态生命周期 bug：请求 abort、streaming、chunked prefill、grammar pending、spec verify 都可能改变同一个 batch。
- KV 分配失败不一定是 OOM，也可能是 prefix cache 锁住了太多节点或 page reserve 估计不对。
- 改采样参数时要同时检查 tokenizer manager 的输入校验、scheduler 的 batch 合并、sampling batch info 的 tensor 化。
"""
            ),
        ],
    )


def nb04():
    write_notebook(
        "04_structured_outputs_fsm.ipynb",
        "04. Structured Outputs：Grammar、Token Mask 与 Compressed FSM",
        [
            COMMON_SETUP,
            md(
                """
## 从用户视角到实现视角

用户传入 JSON schema、regex、EBNF 或 structural tag。实现上，SGLang 要在每一步采样前知道：

> 当前 grammar 状态下，词表中哪些 token 仍然合法？

因此 structured outputs 的核心不是“生成 JSON 字符串”，而是：

1. 把约束编译成 grammar object / matcher / FSM。
2. 每步根据当前状态填充 token bitmask。
3. 在 logits 上应用 mask。
4. 采样 token 后调用 `accept_token` 推进 grammar 状态。
5. 对确定性片段尝试 jump-forward，跳过逐 token 解码。
"""
            ),
            code(
                r"""
for path in [
    "python/sglang/srt/constrained/base_grammar_backend.py",
    "python/sglang/srt/constrained/grammar_manager.py",
    "python/sglang/srt/constrained/xgrammar_backend.py",
    "python/sglang/srt/constrained/outlines_backend.py",
    "python/sglang/srt/constrained/outlines_jump_forward.py",
]:
    print("\n==", path)
    for row in find_defs(path, names={"BaseGrammarObject", "BaseGrammarBackend", "GrammarManager", "XGrammarGrammar", "XGrammarGrammarBackend", "OutlinesJumpForwardMap"}):
        print(row)
"""
            ),
            md(
                """
## `BaseGrammarObject` 是采样循环看到的接口

无论后端是 xgrammar、llguidance 还是 outlines，scheduler/sampling 层关心的接口是一组共同方法：

- `fill_vocab_mask`
- `apply_vocab_mask`
- `accept_token`
- `rollback`
- `try_jump_forward`
- `jump_and_retokenize`

这也是新增 grammar backend 时最重要的 contract。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/constrained/base_grammar_backend.py", 30, 115)
"""
            ),
            guide(
                "`BaseGrammarObject`：采样循环只依赖这组状态机方法",
                "python/sglang/srt/constrained/base_grammar_backend.py",
                30,
                113,
                [
                    "`accept_token` 是状态机前进；采样出 token 后必须调用它，否则下一步 mask 会停在旧状态。",
                    "`allocate_vocab_mask` / `fill_vocab_mask` / `apply_vocab_mask` 把 grammar 状态转成 logits 过滤。",
                    "`rollback` 是 speculative/jump-forward/retokenize 场景的保险丝，允许撤回若干 token 后重放。",
                    "`try_jump_forward` 和 `jump_and_retokenize` 是 compressed FSM 加速的接口，不是所有 backend 都必须成功返回。",
                ],
            ),
            md(
                """
## GrammarManager：异步编译与队列

Grammar 编译可能比普通请求准备更慢。SGLang 不会让未编译完成的请求直接进入 waiting queue，而是放入 `grammar_queue`。编译结果会缓存；多 rank 下还要同步哪些请求 ready/failed。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/constrained/grammar_manager.py", 55, 145)
"""
            ),
            guide(
                "`GrammarManager.process_req_with_grammar`：请求什么时候被拦在 grammar queue",
                "python/sglang/srt/constrained/grammar_manager.py",
                83,
                134,
                [
                    "只要 sampling params 中有 JSON schema、regex、EBNF 或 structural tag，就会构造 cache key。",
                    "`get_cached_or_future_value` 可能返回现成 grammar，也可能返回 Future；Future 未完成时请求不能进入普通 waiting queue。",
                    "invalid grammar 会被缓存为 `InvalidGrammarObject`，避免同一个坏 schema 反复编译。",
                    "strict thinking 复用同一套 grammar/token filter 机制，所以这里还处理 reasoning budget。",
                ],
            ),
            guide(
                "`GrammarManager.get_ready_grammar_requests`：多 rank 下 ready/failed 要同步",
                "python/sglang/srt/constrained/grammar_manager.py",
                136,
                212,
                [
                    "单机时 ready set 可以直接使用；分布式时 ready 取交集，failed 取并集，偏保守保证各 rank 一致。",
                    "编译超时后会 cancel Future，并把失败对象写入 grammar backend cache。",
                    "这段解释了为什么 structured output 请求有时会先等待 grammar preprocessing，而不是立即进入 scheduler。",
                ],
            ),
            md(
                """
## XGrammar backend：token bitmask 路径

`XGrammarGrammarBackend` 使用 tokenizer 信息创建 `GrammarCompiler`，dispatch JSON/regex/EBNF 得到 compiled grammar。`XGrammarGrammar` 持有 `GrammarMatcher`，每步填 bitmask，然后在 GPU logits 上应用 bitmask。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/constrained/xgrammar_backend.py", 59, 130)
show_lines("python/sglang/srt/constrained/xgrammar_backend.py", 188, 245)
"""
            ),
            guide(
                "`XGrammarGrammar`：matcher 状态如何变成 token bitmask",
                "python/sglang/srt/constrained/xgrammar_backend.py",
                59,
                125,
                [
                    "`GrammarMatcher.accept_token` 是 xgrammar 的状态推进；SGLang 额外记录 accepted tokens 方便报错和 rollback。",
                    "`fill_next_token_bitmask` 把下一步合法 token 写入 bitmask；后续 logits kernel 只看这个 bitmask。",
                    "`apply_vocab_mask` 按设备选择 Triton/CUDA/NPU kernel，因此 CPU-only 环境适合读/编译，不适合执行 mask kernel。",
                ],
            ),
            guide(
                "`XGrammarGrammarBackend`：tokenizer 信息决定 grammar 能否编译",
                "python/sglang/srt/constrained/xgrammar_backend.py",
                188,
                245,
                [
                    "backend 初始化时先把 Hugging Face tokenizer 转成 `TokenizerInfo`，失败则可能降级为 grammar_backend=none。",
                    "`model_eos_token_ids` 被传入 tokenizer info，确保 grammar stop token 与模型 EOS 语义一致。",
                    "`is_support_token_filter` 返回 True，strict thinking 等功能会检查这个能力。",
                ],
            ),
            md(
                """
## Compressed FSM / Jump-forward 是什么

在 regex/FSM 约束里，某些状态后面只有一条确定路径。例如 schema 中固定的字段名、标点、引号。逐 token 生成这些确定片段会浪费 decode 步。

SGLang 的 jump-forward 思路是：如果当前 FSM 状态能确定接下来的一段字符串，就直接生成这段字符串，再重新 tokenization / 更新 grammar 状态。`outlines_jump_forward.py` 中的注释直接写着 “Faster constrained decoding with jump forward decoding / compressed finite state machine.”
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/constrained/outlines_jump_forward.py", 1, 40)
show_lines("python/sglang/srt/constrained/outlines_jump_forward.py", 144, 176)
"""
            ),
            guide(
                "`OutlinesJumpForwardMap`：把确定性 FSM 边压缩成可跳过片段",
                "python/sglang/srt/constrained/outlines_jump_forward.py",
                62,
                110,
                [
                    "`init_state_to_jump_forward` 遍历 FSM 边，只保留那些从某状态出发没有歧义的确定边。",
                    "一旦发现同一 state 有多个可行 symbol/byte，就删除 jump-forward 记录，避免错误跳过采样。",
                    "这就是 compressed FSM 的直觉：把线性确定路径压缩成一次字符串推进。",
                ],
            ),
            md(
                """
## 小测试：检查当前环境可用的 grammar 后端

这个测试不启动模型。它检查依赖是否可 import，并定位 SGLang 注册逻辑。Mac 上如果没有 GPU，`apply_vocab_mask` 的 CUDA/Triton 路径不应执行，但编译侧依赖仍可检查。
"""
            ),
            code(
                r"""
for mod in ["xgrammar", "outlines", "llguidance"]:
    try:
        __import__(mod)
        print(mod, "available")
    except Exception as e:
        print(mod, "not available:", type(e).__name__, str(e)[:120])

show_lines("python/sglang/srt/constrained/base_grammar_backend.py", 205, 270)
"""
            ),
            md(
                """
## 贡献者注意点

- Grammar object 必须可复制，因为缓存里保存的是“初始 grammar”，每个请求要拿自己的状态副本。
- Jump-forward 需要 retokenize，tokenizer 的 byte/string 边界非常容易出错。
- 多 rank 下 grammar ready/failed 的同步必须保守，否则不同 rank 会对同一 batch 使用不同约束。
- Reasoning model 的 strict thinking 会复用 grammar/token filter 机制，不要把 structured output 简化成“JSON only”。
"""
            ),
        ],
    )


def nb05():
    write_notebook(
        "05_speculative_decoding.ipynb",
        "05. Speculative Decoding：Draft、Verify、Accept",
        [
            COMMON_SETUP,
            md(
                """
## 统一心智模型

Speculative decoding 的共同目标是减少 target model 的 decode 次数：

1. draft 产生多个候选 token。
2. target 一次 verify 这些候选。
3. accept/reject 决定提交几个 token。
4. KV cache、seq len、输出 token、采样状态一起前进。

不同算法的差异在 draft 来源：

- `EAGLE` / `EAGLE3`：用 draft model / hidden states 预测树状候选。
- `STANDALONE`：小 draft model 独立生成候选。
- `NGRAM`：从历史 ngram 中检索候选，不需要 draft KV。
- `DFLASH` / `FROZEN_KV_MTP`：更新的内部路径，围绕 target hidden / frozen KV / block verify 做优化。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/speculative/spec_info.py", 20, 120)
"""
            ),
            guide(
                "`SpeculativeAlgorithm`：算法能力比 enum 名字更重要",
                "python/sglang/srt/speculative/spec_info.py",
                20,
                120,
                [
                    "`from_string` 同时解析内建算法和插件注册算法，所以调用方不能假设返回值一定是 Enum。",
                    "`is_eagle` 把 EAGLE、EAGLE3、FROZEN_KV_MTP 归入同一族，是因为 scheduler 视角上它们共享 draft hidden/KV 约束。",
                    "`has_draft_kv` 区分 NGRAM 这种不写 draft KV 的算法，直接影响每步 KV reserve 估算。",
                    "`need_topk` 决定 target/draft forward 是否需要额外 top-k 信息。",
                ],
            ),
            md(
                """
## `SpeculativeAlgorithm` 是调度分发的统一接口

注意这里不是简单 enum。插件也可以注册 custom speculative algorithm，但必须 duck-type 出相同的 `is_*` / `supports_*` 接口。这样 scheduler/model runner 可以统一调用。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/speculative/spec_registry.py", 24, 125)
show_lines("python/sglang/srt/speculative/spec_info.py", 150, 225)
"""
            ),
            guide(
                "`CustomSpecAlgo`：插件算法必须 duck-type 内建接口",
                "python/sglang/srt/speculative/spec_registry.py",
                24,
                118,
                [
                    "自定义算法不是随便注册一个名字；它要暴露和 `SpeculativeAlgorithm` 相同的 `is_*` / `supports_*` 方法。",
                    "`supports_overlap=False` 会影响 overlap schedule，可见 spec worker 和 scheduler 并不是松耦合插件。",
                    "如果插件算法要复用 EAGLE 分支，通常要提供自定义 `spec_class` 覆盖对应谓词。",
                ],
            ),
            guide(
                "`create_worker`：算法名最后落到 worker 类",
                "python/sglang/srt/speculative/spec_info.py",
                160,
                224,
                [
                    "DFLASH、FROZEN_KV_MTP、EAGLE、STANDALONE、NGRAM 都在这里映射到不同 worker。",
                    "EAGLE-family 默认使用 V2 worker，说明旧 spec worker 路径已经不是主线。",
                    "新增内建算法时，除了 server args hook，还要在这里定义 worker 映射。",
                ],
            ),
            md(
                """
## Worker 分层

`BaseSpecWorker` 管理 target worker 与 draft worker 的关系。EAGLE V2 worker 中可以看到：

- target forward 捕获 hidden states 或 logits。
- draft 根据 hidden/last token 生成候选。
- verify 让 target 检查候选。
- accept/reject kernel 计算接受长度和 bonus token。
- 更新 batch result，让 scheduler 像普通 decode 一样继续处理输出。
"""
            ),
            code(
                r"""
for path in [
    "python/sglang/srt/speculative/base_spec_worker.py",
    "python/sglang/srt/speculative/eagle_worker_v2.py",
    "python/sglang/srt/speculative/ngram_worker.py",
    "python/sglang/srt/speculative/reject_sampling.py",
]:
    print("\n==", path)
    for lineno, kind, name in find_defs(path):
        if name in {"BaseSpecWorker", "EagleDraftWorkerBase", "EAGLEWorkerV2", "EagleDraftWorker", "NGRAMWorker", "draft", "verify", "draft_extend"}:
            print(f"{lineno:4d} {kind:16s} {name}")
"""
            ),
            guide(
                "`BaseSpecWorker`：target worker 和 draft worker 的共同 contract",
                "python/sglang/srt/speculative/base_spec_worker.py",
                274,
                324,
                [
                    "`target_worker` 和 `draft_worker` 是抽象属性；算法可以共享 target runner，也可以有独立 draft runner。",
                    "`resolve_model_worker_batch` 默认按 target batch 解析，复杂算法会覆盖以适配 draft/verify 的 metadata。",
                    "`finalize_after_verify` 是 accept counts 回到 CPU 后的 hook，用于更新 KV 或算法运行时状态。",
                ],
            ),
            guide(
                "`EAGLEWorkerV2` 的 target/draft 关系",
                "python/sglang/srt/speculative/eagle_worker_v2.py",
                937,
                1088,
                [
                    "`target_worker` 是主模型，`draft_worker` 包装 draft runner；两者共享或协调 KV allocator。",
                    "prefill 时 target 先 forward，并以 hidden states/next token 驱动 draft extend。",
                    "`capture_hidden_mode` 是 EAGLE 族的关键：draft 不是只看 token，还依赖 target hidden。",
                ],
            ),
            md(
                """
## Accept/reject 的正确性

Greedy verify 可以比较 draft token 与 target top-1；采样场景更复杂，需要 rejection sampling，确保输出分布仍等价于 target model。`reject_sampling.py` 里实现的是接受路径与最终 token 的概率修正。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/speculative/reject_sampling.py", 1, 45)
show_lines("python/sglang/srt/speculative/reject_sampling.py", 90, 125)
"""
            ),
            guide(
                "`reject_sampling.py`：拒绝采样的核心分支",
                "python/sglang/srt/speculative/reject_sampling.py",
                44,
                124,
                [
                    "kernel 逐步比较 draft token 在 target/draft 概率下是否可接受，接受则推进 `last_accepted_global_idx`。",
                    "一旦拒绝，最终 token 不再直接用 draft，而从修正后的 target-minus-draft 分布采样。",
                    "全部接受时还要采一个 bonus token，这就是 accept_lens 往往包含 bonus 的原因。",
                ],
            ),
            md(
                """
## KV cache 为什么是难点

Speculative decoding 不只是多生成几个 token。draft token 可能被拒绝，因此 KV 写入需要区分：

- draft KV 是否真实写入。
- target verify 使用哪段 cache loc。
- 接受后哪些 KV 要搬到 committed target KV。
- 拒绝后哪些临时 KV 要释放或覆盖。

这就是为什么 speculative 代码里会有 cache loc kernel、future map、verify buffer、draft/target attention backend 之间的同步。
"""
            ),
            code(
                r"""
for path in [
    "python/sglang/srt/speculative/triton_ops/cache_locs.py",
    "python/sglang/srt/speculative/triton_ops/eagle.py",
    "python/sglang/srt/speculative/eagle_utils.py",
]:
    print("\n==", path)
    matches = [line for line in read_rel(path).splitlines() if "cache" in line.lower() or "accept" in line.lower()]
    for line in matches[:20]:
        print(line[:140])
"""
            ),
            md(
                """
## 小测试：算法名解析和插件保留名

这个测试只跑 Python enum/registry，不需要模型。
"""
            ),
            code(
                r"""
from sglang.srt.speculative.spec_info import SpeculativeAlgorithm

for name in [None, "EAGLE", "eagle3", "standalone", "ngram", "none"]:
    algo = SpeculativeAlgorithm.from_string(name)
    print(name, "->", algo, "is_some=", algo.is_some(), "need_topk=", algo.need_topk() if hasattr(algo, "need_topk") else None)

try:
    SpeculativeAlgorithm.from_string("not-a-real-algo")
except ValueError as e:
    print("unknown name:", e)
"""
            ),
            md(
                """
## 贡献者注意点

- 新算法如果要进入主干，先明确它是否需要 draft KV、是否支持 overlap、是否需要 target hidden states。
- 所有 accept length 都会影响 scheduler 的输出 token 数、KV 提交数、metrics 和 finish 判断。
- 调试 spec decoding 时，先用 batch size 1、temperature 0、短 prompt 验证 token 序列，再放大到 overlap/batching。
"""
            ),
        ],
    )


def nb06():
    write_notebook(
        "06_hicache_disaggregation_new_features.ipynb",
        "06. HiCache、Disaggregation 与新特性落点",
        [
            COMMON_SETUP,
            md(
                """
## HiCache 是 RadixAttention 的分层扩展

RadixAttention 把可复用 KV 留在 GPU 空闲空间中。HiCache 把这个想法扩展为：

- L1：GPU KV cache。
- L2：本机 host memory KV cache。
- L3：跨实例共享的外部存储，如 Mooncake、HF3FS、NIXL、AIBrix、file backend。

关键变化是 metadata tree 需要同时知道 device/host/storage 的命中情况，prefill 需要把 host/storage 命中的 KV load back 到 GPU。
"""
            ),
            code(
                r"""
for path in [
    "docs/advanced_features/hicache_design.md",
    "python/sglang/srt/mem_cache/hiradix_cache.py",
    "python/sglang/srt/managers/cache_controller.py",
    "python/sglang/srt/mem_cache/hicache_storage.py",
]:
    print("\n==", path)
    print((ROOT / path).exists())
"""
            ),
            md(
                """
## HiRadixCache 的关键状态

`HiRadixCache` 继承 `RadixCache`，但节点上除了 device value，还可能有 host value、write-through pending id、hash values。它通过 `HiCacheController` 处理 GPU<->CPU 和 CPU<->L3 的传输。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/mem_cache/hiradix_cache.py", 72, 185)
"""
            ),
            guide(
                "`HiRadixCache.__init__`：在 RadixCache 外面加 L2/L3 控制器",
                "python/sglang/srt/mem_cache/hiradix_cache.py",
                72,
                185,
                [
                    "根据底层 KV pool 类型创建 host pool；MHA、MLA、DSA 的 host memory layout 不同。",
                    "`enable_storage` 由 storage backend 是否存在决定；只开 L2 和开 L3 是两种不同模式。",
                    "`HiCacheController` 接管 GPU<->CPU 和 CPU<->storage 的异步传输，Radix tree 仍负责 metadata。",
                    "`ongoing_write_through`、`ongoing_load_back`、`ongoing_prefetch` 是防止异步 I/O 和 tree mutation 打架的关键账本。",
                ],
            ),
            md(
                """
## 三个动作：local match、prefetch、write-back

- `match_prefix`：先查本地 tree，返回 device hit + host hit。
- `load_back` / `init_load_back`：把 host hit 的 KV 搬回 device。
- `prefetch_from_storage` / `check_prefetch_progress`：从 L3 异步预取到 host。
- `write_backup` / `write_backup_storage`：把热 KV 或被驱逐 KV 写回 host/storage。
"""
            ),
            code(
                r"""
for name in ["match_prefix", "load_back", "init_load_back", "prefetch_from_storage", "check_prefetch_progress", "write_backup", "write_backup_storage", "evict"]:
    rows = find_defs("python/sglang/srt/mem_cache/hiradix_cache.py", {name})
    print(name, rows)
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/mem_cache/hiradix_cache.py", 1241, 1345)
show_lines("python/sglang/srt/mem_cache/hiradix_cache.py", 1438, 1530)
"""
            ),
            guide(
                "`init_load_back`：L2 host hit 什么时候搬回 GPU",
                "python/sglang/srt/mem_cache/hiradix_cache.py",
                1212,
                1265,
                [
                    "`best_match_node` 是 load-back 的锚点，普通 RadixCache 不需要这个复杂度，HiCache 需要。",
                    "如果 L3 启用且 host hit 后还有足够长的 storage 可能命中，会触发 prefetch。",
                    "load-back 和 prefetch 是两个层级：前者把 L2 -> L1，后者把 L3 -> L2。",
                ],
            ),
            guide(
                "`prefetch_from_storage`：L3 预取先占 host page，再异步发起 I/O",
                "python/sglang/srt/mem_cache/hiradix_cache.py",
                1471,
                1530,
                [
                    "`prefetch_key` 会按 page 对齐，避免 L3 读写粒度和 host pool 粒度不一致。",
                    "如果 host pool 不够，会先 `evict_host`，仍不够则缩短预取长度或放弃。",
                    "`ongoing_prefetch[req_id]` 记录 last_host_node、key、host_indices、operation，后续 progress/terminate 依赖这份账本。",
                ],
            ),
            md(
                """
## HiCacheController：后台线程与传输队列

Controller 把同步调度路径和慢 I/O 分开：

- write queue 合并 GPU->host 写入。
- prefetch queue / aux thread 处理 L3->host。
- ack queue 告诉 scheduler 哪些异步写已经完成。
- rate limit 避免 prefetch 占用过多 host pool。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/managers/cache_controller.py", 209, 305)
show_lines("python/sglang/srt/managers/cache_controller.py", 870, 910)
show_lines("python/sglang/srt/managers/cache_controller.py", 1024, 1070)
"""
            ),
            guide(
                "`HiCacheController.write`：把多次写合并到异步 write stream",
                "python/sglang/srt/managers/cache_controller.py",
                656,
                719,
                [
                    "`write_queue` 先收集多个 cache operation，再 `merge_ops` 减少传输碎片。",
                    "page-first layout 可能走 JIT write-back kernel，说明 host layout 是性能参数，不只是存储格式。",
                    "`ack_write_queue` 用 start/finish event 把异步写完成状态交还给 scheduler。",
                ],
            ),
            guide(
                "`prefetch_thread_func`：L3 命中数不足时会撤销预取",
                "python/sglang/srt/managers/cache_controller.py",
                1024,
                1070,
                [
                    "storage prefetch 在后台线程里查询命中数量，并用 all-reduce 同步多 rank 结果。",
                    "命中 token 少于 `prefetch_threshold` 时不会真的发起 I/O，而是把 request id 放进 revoke queue。",
                    "这解释了 HiCache 不是“看到 L3 就读”，而是用阈值控制 latency/benefit tradeoff。",
                ],
            ),
            md(
                """
## Disaggregation：prefill/decode 分离为什么会影响 KV

PD disaggregation 把 prefill 和 decode 放到不同节点/进程。这样 prefill 产生的 KV 要跨节点交给 decode。HiCache 可以在 prefill/decode 节点上同时启用，用 L3 降低重复 prefill。

源码入口：

- `python/sglang/srt/disaggregation/prefill.py`
- `python/sglang/srt/disaggregation/decode.py`
- `python/sglang/srt/disaggregation/*/conn.py`
- `python/sglang/srt/disaggregation/kv_events.py`
"""
            ),
            code(
                r"""
for path in [
    "python/sglang/srt/disaggregation/prefill.py",
    "python/sglang/srt/disaggregation/decode.py",
    "python/sglang/srt/disaggregation/kv_events.py",
]:
    print("\n==", path)
    for lineno, kind, name in find_defs(path):
        if "KV" in name or "Disagg" in name or name in {"PrefillBootstrapQueue", "DecodeScheduler"}:
            print(f"{lineno:4d} {kind:16s} {name}")
"""
            ),
            md(
                """
## 新特性常见落点

你看到 Advanced Features 新增页面时，可以先判断它属于哪类：

- **请求语义类**：采样参数、reasoning、tool parser、structured outputs。通常改 `io_struct.py`、OpenAI protocol、TokenizerManager、sampling。
- **调度/缓存类**：chunked prefill、Radix/HiCache、pause/resume、priority。通常改 Scheduler、ScheduleBatch、mem_cache。
- **执行优化类**：attention backend、CUDA graph、quantization、MoE。通常改 model_executor、layers、jit_kernel。
- **部署拓扑类**：PD/EPD disaggregation、gateway、multi-node。通常改 entrypoints、disaggregation、connector。
- **模型支持类**：新增 architecture。通常改 `srt/models`、weight loader、model registry、测试。
"""
            ),
            code(
                r"""
advanced = sorted((ROOT / "docs" / "advanced_features").glob("*.md")) + sorted((ROOT / "docs" / "advanced_features").glob("*.ipynb"))
for p in advanced:
    print(p.name)
"""
            ),
            md(
                """
## 贡献者注意点

- HiCache 的正确性高度依赖多 rank 同步，任何“本 rank 看起来可以”的判断都要检查 all-reduce/barrier。
- L3 storage backend 不应泄漏模型执行细节；统一接口在 `HiCacheStorage`。
- 新 feature 如果改变 KV 生命周期，要同时考虑普通 RadixCache 和 HiRadixCache。
"""
            ),
        ],
    )


def nb07():
    write_notebook(
        "07_contributor_playbook.ipynb",
        "07. 贡献者实战路线：如何读、改、测一个 Feature",
        [
            COMMON_SETUP,
            md(
                """
## 一条推荐工作流

1. 从 docs 找到用户 API：参数名、endpoint、示例。
2. 在 `ServerArgs` / `io_struct` / OpenAI protocol 中找输入字段。
3. 跟踪字段进入 `TokenizerManager`、`Req`、`ScheduleBatch`。
4. 找 scheduler 决策点：入队、batch formation、run_batch、process result。
5. 找执行点：model runner、attention backend、sampling、grammar/spec/cache worker。
6. 找测试：unit test、kit、server fixture、nightly/performance test。
7. 写最小复现，再写覆盖真实边界条件的测试。
"""
            ),
            guide(
                "`Req` 字段是 Feature 进入 scheduler 的常见落点",
                "python/sglang/srt/managers/schedule_batch.py",
                666,
                745,
                [
                    "如果你的 Feature 是每请求语义，先问它是否需要成为 `Req` 字段。",
                    "字段一旦进 `Req`，就要考虑 batch 合并、streaming 返回、abort 清理、测试 fixture。",
                    "不要把 API 层字段直接塞进 model runner；中间的 scheduler 状态会决定它是否能安全跨进程/跨 batch。",
                ],
            ),
            guide(
                "`BasePrefixCache` 是 cache 类 Feature 的稳定接口",
                "python/sglang/srt/mem_cache/base_prefix_cache.py",
                172,
                245,
                [
                    "新增 cache 实现必须覆盖 match/insert/cache_finished/cache_unfinished/evict/lock-ref 这些生命周期方法。",
                    "`MatchResult` 字段已经为 HiCache/Mamba/SWA 预留多种 hit 类型，新增 cache 行为应优先复用这些语义。",
                    "如果你只改 RadixCache 而没看 BasePrefixCache，往往会漏掉 ChunkCache/HiRadixCache/UnifiedCache 的兼容性。",
                ],
            ),
            md(
                """
## 常用 grep 模式

SGLang 很大，盲读会很累。建议从这些模式开始：
"""
            ),
            code(
                r"""
patterns = [
    "rg -n \"参数名|类名|函数名\" python/sglang docs test",
    "rg -n \"class .*Backend|register_.*backend|REGISTRY\" python/sglang/srt",
    "rg -n \"sampling_params\\.|server_args\\.|req\\.\" python/sglang/srt/managers",
    "rg -n \"cache_finished_req|match_prefix|alloc_for_extend|evict\" python/sglang/srt",
    "rg -n \"SpeculativeAlgorithm|grammar_backend|attention_backend\" python/sglang/srt",
]
for p in patterns:
    print(p)
"""
            ),
            md(
                """
## 测试入口地图

这个仓库的测试分层明显：

- `python/sglang/test/kits`：可复用测试 kit，很多功能正确性都在这里。
- `python/sglang/test/server_fixtures`：不同 server 配置的 fixture。
- `test/`：项目根目录下也有集成/端到端测试。
- docs notebook：能验证示例，但不应当是唯一测试。
"""
            ),
            code(
                r"""
for d in [
    "python/sglang/test/kits",
    "python/sglang/test/server_fixtures",
    "python/sglang/test",
    "test",
]:
    path = ROOT / d
    if path.exists():
        files = sorted(path.glob("*.py"))
        print(f"\n{d}: {len(files)} python files")
        for f in files[:20]:
            print(" -", f.name)
"""
            ),
            md(
                """
## 小测试：给 Feature 找测试

下面输入关键词，cell 会找相关测试文件。你可以改 `keyword`。
"""
            ),
            code(
                r"""
keyword = "radix"
roots = [ROOT / "python" / "sglang" / "test", ROOT / "test"]
for root in roots:
    if not root.exists():
        continue
    print("\n==", root.relative_to(ROOT))
    for p in sorted(root.rglob("*.py")):
        text = p.read_text(errors="ignore")
        if keyword.lower() in text.lower() or keyword.lower() in p.name.lower():
            print(p.relative_to(ROOT))
"""
            ),
            md(
                """
## 修改不同类型 Feature 的最小检查清单

### 新 server 参数

- `server_args.py` 是否定义、校验、默认值合理。
- docs 是否说明默认行为和适用硬件。
- 参数是否参与 metrics / logs，便于线上定位。

### 新调度策略

- waiting queue 和 running batch 的状态是否一致。
- abort、timeout、streaming、grammar pending、chunked prefill 是否安全。
- KV reserve 估计是否保守。

### 新 cache 行为

- prefix key 是否包含隔离维度。
- lock/ref 是否覆盖所有异步路径。
- evict 是否释放了正确 pool。
- page_size > 1 是否正确。

### 新 grammar backend

- grammar object 是否可 copy。
- mask shape、device、vocab size 是否一致。
- jump-forward 是否保持 tokenizer/grammar 状态一致。

### 新 speculative 算法

- accept length、bonus token、KV commit、metrics 是否一致。
- overlap disabled/enabled 是否都能工作，或明确禁止。
- draft/target vocab 不一致时是否报错。
"""
            ),
            md(
                """
## 建议先读的几个源码片段

如果你只想用一天快速熟悉 SGLang，按这个顺序读：

1. `docs/index.rst`：Feature 总目录。
2. `python/sglang/launch_server.py`：启动分流。
3. `python/sglang/srt/entrypoints/engine.py`：manager 初始化。
4. `python/sglang/srt/managers/tokenizer_manager.py::generate_request`。
5. `python/sglang/srt/managers/scheduler.py::event_loop_*`、`get_new_batch_prefill`、`run_batch`。
6. `python/sglang/srt/managers/schedule_batch.py` 顶部注释和 `Req`。
7. `python/sglang/srt/mem_cache/radix_cache.py`。
8. 任选一个 Feature：structured outputs、speculative、HiCache，按前几本指南深入。
"""
            ),
            code(
                r"""
must_read = [
    "docs/index.rst",
    "python/sglang/launch_server.py",
    "python/sglang/srt/entrypoints/engine.py",
    "python/sglang/srt/managers/tokenizer_manager.py",
    "python/sglang/srt/managers/scheduler.py",
    "python/sglang/srt/managers/schedule_batch.py",
    "python/sglang/srt/mem_cache/radix_cache.py",
]
for p in must_read:
    print(p, "exists=", (ROOT / p).exists())
"""
            ),
            md(
                """
## 最后的判断标准

你真正理解一个 SGLang Feature，通常意味着你能回答：

- 用户 API 是什么，默认行为是什么？
- 请求对象在哪个字段携带它？
- scheduler 在哪一步看见它？
- 它是否改变 KV cache、batch shape、sampling 或 output streaming？
- 它失败时用户会看到什么错误？
- 它的最小测试和压力测试分别是什么？
"""
            ),
        ],
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    nb00()
    nb01()
    nb02()
    nb03()
    nb04()
    nb05()
    nb06()
    nb07()
    print(f"Wrote notebooks to {OUT}")


if __name__ == "__main__":
    main()

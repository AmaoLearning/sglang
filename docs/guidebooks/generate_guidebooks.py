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
    "suppress_noisy_warnings": "启动入口先压掉第三方库的已知噪声 warning，让真正的启动错误更容易被看到。",
    "launch_server": "`run_server` 的默认 HTTP/SRT 路径；真正的 manager 子进程装配在 `http_server.launch_server` 里完成。",
    "serve_grpc_encoder": "encoder-only + gRPC 的专用服务路径，用于 embedding/encoder 类模型而不是普通生成式 HTTP server。",
    "serve_grpc": "普通生成模型的 gRPC 服务路径；它绕开默认 FastAPI/uvicorn HTTP 入口。",
    "run_expert_backup_manager": "启动 DeepEP MoE expert 备份管理器，只在启用 expert distribution recorder 且当前节点需要维护冗余专家时运行。",
    "launch_dummy_health_check_server": "非 0 rank 不承载完整 HTTP API 时仍暴露健康检查端口，方便外部编排系统判断子节点存活。",
    "configure_logger": "按 server args 配置 SRT 进程日志；这一步发生在子进程启动前，保证 scheduler/detokenizer 日志格式一致。",
    "_set_envs_and_config": "把 server args 转成运行时环境变量和全局配置，后续 model runner、通信库和 cache 逻辑会读取这些开关。",
    "_set_gc": "按 server args 调整 Python GC 行为，避免长生命周期服务在请求热路径上频繁触发不可控 GC pause。",
    "resolve_auto_parsers": "在 scheduler 启动前解析 `reasoning_parser/tool_call_parser=auto`，让 tokenizer/template 侧不用再猜 parser 类型。",
    "cls._launch_scheduler_processes": "启动 scheduler/model worker 进程；模型加载、TP/DP 通信组和 scheduler capability 都从这里产生。",
    "cls._launch_detokenizer_subprocesses": "启动 detokenizer 进程，把 token id 到文本的 CPU 工作从 scheduler 中拆出去。",
    "MultiTokenizerRouter": "多 tokenizer worker 模式下的主进程路由器；HTTP worker 的请求不会直接共用单个 TokenizerManager。",
    "scheduler_init_result.all_child_pids.append": "把 detokenizer 子进程 PID 纳入 scheduler 初始化结果，后续 watchdog/清理逻辑才能统一管理。",
    "processes.extend": "把 detokenizer 进程追加到 watchdog 监控集合，主进程会同时观察 scheduler 与 detokenizer。",
    "names.extend": "给 watchdog 中新增的 detokenizer 进程补上可读名称，崩溃日志能指出是哪类子进程失败。",
    "subprocess_watchdog.start": "启动后台 watchdog 线程，子进程异常退出会被主进程发现并转成服务级故障。",
    "Engine._launch_subprocesses": "启动并连接 SRT engine 的内部组件，返回 manager、IPC 端口、scheduler 初始化信息和 watchdog。",
    "_setup_and_run_http_server": "把已经启动的 engine 组件挂到 FastAPI app 上，并启动 HTTP server。",
    "set_global_state": "把 manager/template/scheduler 信息放入 HTTP 全局状态，endpoint 之后通过它拿到 runtime 对象。",
    "_GlobalState": "HTTP 全局状态对象；FastAPI endpoint 后续通过它拿 tokenizer manager、template manager 和 scheduler info。",
    "write_data_for_multi_tokenizer": "多 tokenizer worker 模式下通过共享内存传递启动参数。",
    "add_api_key_middleware": "把 API key/admin API key 鉴权逻辑注册到 FastAPI middleware。",
    "add_prometheus_track_response_middleware": "在 FastAPI 层增加 response metrics middleware，使 HTTP 请求耗时和状态码进入 Prometheus 指标。",
    "app_has_admin_force_endpoints": "检查当前 FastAPI app 是否暴露强制类管理 endpoint；有这类 endpoint 时必须打开 admin key 校验。",
    "set_uvicorn_logging_configs": "把 SGLang 的日志配置同步给 uvicorn，避免 HTTP server 使用另一套默认日志格式。",
    "uvicorn.run": "启动默认 ASGI HTTP server，真正开始监听请求。",
    "_run_granian_server": "启动 Granian HTTP/2 server，是 HTTP/2 路径的替代 server backend。",
    "PortArgs.init_new": "分配 tokenizer/scheduler/detokenizer 之间 IPC 通信所需的端口或 socket 名称。",
    "load_plugins": "加载插件，让插件有机会注册模型、参数 hook 或 speculative/grammar 扩展。",
    "server_args.check_server_args": "在进程启动前做参数一致性校验，避免子进程启动后才失败。",
    "scheduler_init_result.wait_for_ready": "等待 scheduler/model worker 完成初始化并回传可服务状态。",
    "SubprocessWatchdog": "监控 scheduler/detokenizer 子进程存活，避免主进程静默挂着坏服务。",
    "start_cpu_monitor_thread": "为 tokenizer/detokenizer 进程启动 CPU 监控线程，便于定位 CPU 侧预处理或 detokenize 阻塞。",
    "configure_gc_warning": "启用 GC pause 告警；tokenizer manager 是长生命周期进程，GC 卡顿会直接影响请求入站延迟。",
    "Watchdog.create": "为 tokenizer manager 创建软 watchdog，用于发现 handle loop 或请求处理长时间无进展。",
    "TypeBasedDispatcher": "按返回对象类型分发处理函数，减少 tokenizer manager 中的 if/else 回包分支。",
    "self.init_communicators": "初始化 tokenizer manager 与 scheduler/detokenizer 间的 IPC 通道。",
    "obj.normalize_batch_and_arguments": "把单请求/批请求和参数别名规范化，后续路径才能统一处理。",
    "self._set_default_priority": "为请求补齐默认优先级，供 scheduler priority policy 使用。",
    "self._init_req_state": "创建 rid 到 ReqState 的映射，后续 streaming/non-streaming 回包都靠它找到等待者。",
    "self._tokenize_one_request": "把用户输入文本、多模态数据、chat template 处理成内部 tokenized request。",
    "self._send_one_request": "把 tokenized request 通过 IPC 发给 scheduler。",
    "self._wait_one_response": "等待 scheduler/detokenizer 回包，并按 streaming/non-streaming 产出 API 响应。",
    "self._handle_batch_output": "把 batch 输出拆回每个 rid，并整理 meta_info、文本、logprob、finish reason。",
    "self._attach_multi_http_worker_info": "多 tokenizer worker 模式下给请求补充 HTTP worker IPC 信息，scheduler 回包才能路由回正确 worker。",
    "self._handle_epd_disaggregation_encode_request": "EPD language-only encode 请求的旁路处理；这种请求不进入普通生成式 decode 流程。",
    "self.request_logger.log_received_request": "在请求刚完成规范化后记录输入摘要，便于把用户请求和后续 scheduler 日志串起来。",
    "self._validate_and_resolve_lora": "在 tokenization 前解析并校验 LoRA 选择，确保 cache key 和调度状态带上正确 LoRA 维度。",
    "self.recv_from_detokenizer.recv_pyobj": "从 detokenizer IPC 通道收回 batch 输出或控制对象，这是响应回到 API 层的入口。",
    "self._result_dispatcher": "处理非 batch-output 的控制消息，例如 abort、flush cache、profile 等 manager 间响应。",
    "self.convert_logprob_style": "把 scheduler 返回的 logprob token 信息转换成用户 API 请求的文本/token 风格。",
    "template_manager.initialize_templates": "根据 tokenizer 和 server args 初始化 chat/completion template，并顺带推断 reasoning/tool parser。",
    "get_zmq_socket": "创建 ZeroMQ socket，是 manager 进程之间传对象的底层通道。",
    "get_tokenizer": "加载 Hugging Face 或自定义 tokenizer，供 detokenization 或模板处理使用。",
    "key.page_aligned": "把 key 截到 page 边界，保证命中的 KV span 能被 page allocator 安全复用。",
    "self._match_prefix_helper": "沿 radix tree 递归寻找最长已缓存前缀。",
    "self._split_node": "当匹配在节点中间结束时拆节点，给未来请求留下精确边界。",
    "key.maybe_to_bigram_view": "EAGLE 路径会把 token 序列按 bigram 视图解释，prefix cache 需要用同一套 key 语义匹配 draft/target KV。",
    "tree_cache.match_prefix": "查询 prefix cache，把可复用 KV slot 和节点锚点返回给 scheduler。",
    "zero_match_result": "把一次命中强制归零，常用于调试或禁用 radix 命中的实验。",
    "match_prefix_for_req": "把 cache 命中结果写回 Req，供排序和 KV 分配使用。",
    "ForwardBatch.init_new": "把 scheduler 的 CPU 侧 batch 状态转换为 model runner/attention backend 使用的 tensor 元数据。",
    "self.request_receiver.recv_requests": "scheduler 从 tokenizer manager 拉取新请求和控制消息，每轮调度都先消费这个入口。",
    "self.process_input_requests": "把新请求、abort、flush、update weight 等控制消息并入 scheduler 内部队列。",
    "self.get_next_batch_to_run": "在 running batch 和 waiting queue 之间选择下一批可执行请求，是 continuous batching 的调度入口。",
    "self.on_idle": "scheduler 无 batch 可跑时执行空闲维护，例如健康检查、状态重置或等待新请求。",
    "self._apply_war_barrier": "overlap 调度里处理 write-after-read 依赖屏障，避免上一轮 GPU 结果尚未安全发布就复用资源。",
    "self.is_disable_overlap_for_batch": "检查当前 batch 是否因 grammar/spec/特殊 forward mode 等原因不能和上一批重叠执行。",
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
    "self.draft_worker.draft": "EAGLE decode 路径先让 draft model 生成候选树，返回 target verify 需要的 draft token、tree mask 和索引。",
    "self.draft_worker._draft_extend_for_prefill": "prefill 后用 target hidden/next token 预热 draft KV，并构造下一轮 decode 的 draft input。",
    "self.draft_worker._draft_extend_for_decode": "verify 接受后把 target 结果转成下一轮 draft 所需的 hidden/topk/bonus token 状态。",
    "self.draft_worker.draft_extend": "让 draft worker 基于 target hidden/last token 扩展候选。",
    "self._build_trivial_verify_input": "adaptive spec 把步数降到 0 时，构造一个只采 bonus token 的 verify 输入，相当于退化成普通 decode。",
    "self._stub_skipped_draft_extend": "跳过 0-step draft_extend 时填充形状合法的 next_draft_input，避免 overlap/future_map 读取空字段。",
    "eagle_prepare_for_verify": "把 draft 树展开成 target verify forward batch，包括 tree attention mask、positions 和 out_cache_loc。",
    "eagle_sample": "根据 target logits 和 draft 树执行 accept/reject，返回预测 token、每请求接受长度和接受节点索引。",
    "commit_mamba_states_after_verify": "混合 GDN/Mamba 模型在 verify 后只提交被接受路径对应的状态，拒绝分支不能污染请求状态。",
    "move_accept_tokens_to_target_kvcache": "tree draft 接受路径可能不在每请求 KV block 前部；该函数把 accepted KV 搬到后续 decode 期待的位置。",
    "compute_spec_v2_logprobs": "spec verify 会一次产生多个候选 token，需要按 accept_index 把 logprob 对齐到最终接受路径。",
    "generate_token_bitmask": "structured output 与 speculative verify 结合时，需要基于 draft tree 上每个候选节点生成 grammar mask。",
    "self._prepare_for_speculative_decoding": "NGRAM 路径把 CPU ngram 候选整理成 target-verify batch，替代 EAGLE 的 draft model。",
    "self._update_ngram_corpus": "target verify 结束后把新接受的 token 写回 ngram corpus，下一轮检索才能看到最新上下文。",
    "self.ngram_corpus.erase_match_state": "请求离开 decode batch 后清理 ngram match 状态，避免 corpus 持有已结束请求的游标。",
    "compute_dflash_correct_drafts_and_bonus": "计算 DFLASH greedy verify 下可接受 draft 数和 bonus token。",
    "self.cache_controller.write": "把 device KV 写入 host pool，作为 HiCache L2 备份。",
    "self.cache_controller.write_storage": "把 host KV 写到 L3 storage backend，供跨实例复用。",
    "self.cache_controller.prefetch": "发起从 L3 storage 到 host pool 的异步预取。",
    "self.cache_controller.terminate_prefetch": "结束预取并返回实际完成 token 数。",
    "self.evict_host": "从 host KV pool 中驱逐页面，为新的 load-back/prefetch 腾空间。",
    "self.scripted_scheduler_hook.on_run_batch": "测试/脚本 hook 可在每次 batch 执行前观察或修改 batch，用于调度实验和可控复现。",
    "self.profiler_manager._profile_batch_predicate": "按当前 batch 决定是否启动 profiler，避免对所有请求都付 profiling 开销。",
    "self._run_batch_prebuilt": "PD disaggregation decode 可以直接使用预构建 batch，绕过普通 scheduler 现场组装路径。",
    "self.future_map.resolve_seq_lens_cpu": "overlap 模式下先解析 speculative future indices 对 seq_lens 的影响，保证 CPU 调度看到正确长度。",
    "resolve_forward_inputs": "把 ScheduleBatch 中的 CPU staging 输入解析成 model worker 可消费的 forward 输入。",
    "self._forward_isolation": "overlap forward 前建立 batch 状态隔离，防止 worker 修改污染 scheduler 下一轮准备。",
    "self.future_map.publish": "overlap/speculative 路径把可见 seq_lens 发布给调度线程，使下一轮 CPU 准备可提前进行。",
    "self.model_worker.forward_batch_generation": "进入 TP model worker 执行生成 forward；attention backend、sampling 和 logits 处理从这里往下发生。",
    "req.set_finish_with_abort": "把 grammar 编译不可用或非法 schema 转成请求级 abort，scheduler 后续会把它作为已结束请求处理。",
    "self._apply_request_reasoning_budget": "把 strict thinking/reasoning budget 写入 grammar object，使 reasoning token 数受同一套 token filter 约束。",
    "self.grammar_queue.append": "grammar Future 未完成时请求先留在 grammar_queue，不能进入普通 waiting queue。",
    "self.matcher.accept_token": "把采样出的 token 推进 xgrammar matcher；如果 matcher 拒绝，说明 logits mask 或 retokenize 状态已经不一致。",
    "self.matcher.rollback": "撤回 matcher 的最近 k 个 token，供 speculative reject 或 jump-forward retokenize 后重放。",
    "self.matcher.is_terminated": "查询 grammar 是否已到终止状态，终止后不再推进 token mask。",
    "vocab_mask.to": "把 CPU 侧 token bitmask 异步搬到 logits 所在设备，采样前 mask kernel 才能直接读取。",
    "GrammarCompiler": "用 tokenizer token 边界构建 xgrammar compiler；后续 JSON/regex/EBNF 都依赖它生成 compiled grammar。",
    "TokenizerInfo.from_huggingface": "把 Hugging Face tokenizer 转成 xgrammar 可用的 token 信息，并显式使用模型 EOS 作为 stop token。",
    "get_mha_host_pool_cls": "根据 GPU KV pool 类型选择对应 host pool 布局，HiCache L2 必须和 device KV layout 对齐。",
    "MLATokenToKVPoolHost": "为 MLA KV cache 创建 host 侧镜像池，布局不同于普通 MHA host pool。",
    "self._parse_storage_backend_extra_config": "解析 L3 storage backend 的额外配置，得到预取阈值、超时策略和 prefix-key 传递策略。",
    "attach_hybrid_dsa_pool_to_hiradix_cache": "DSA KV layout 需要专门的 hybrid host pool/controller 装配，不能走普通 MHA/MLA 分支。",
    "HiCacheController": "创建 HiCache 的异步传输控制器，统一管理 device<->host 写回、L3 预取和 ACK 队列。",
    "self._apply_storage_runtime_config": "把 storage backend、阈值、超时和 metrics 配置写入 HiRadixCache 运行时状态。",
}


SUPPRESSED_AUTO_CALL_EXPLANATIONS = {
    # Speculative decoding guide uses hand-written line-level comments for these
    # hot-path calls. The generic call annotation is too repetitive here.
    "self.draft_worker.draft",
    "self.draft_worker._draft_extend_for_prefill",
    "self.draft_worker._draft_extend_for_decode",
    "self._build_trivial_verify_input",
    "self._stub_skipped_draft_extend",
    "eagle_prepare_for_verify",
    "eagle_sample",
    "commit_mamba_states_after_verify",
    "move_accept_tokens_to_target_kvcache",
    "compute_spec_v2_logprobs",
    "generate_token_bitmask",
    "self._prepare_for_speculative_decoding",
    "self._update_ngram_corpus",
    "self.ngram_corpus.erase_match_state",
    "vocab_mask.to",
}


BRANCH_EXPLANATIONS = {
    "server_args.encoder_only": "encoder-only 服务只处理 embedding/encoder 类请求；不会启动普通生成式 HTTP runtime。",
    "server_args.grpc_mode": "选择 gRPC 协议入口，绕过默认 FastAPI/uvicorn endpoint。",
    "server_args.use_ray": "Ray serving 使用分布式 actor 拓扑，启动路径不再由本进程直接装配 SRT 子进程。",
    "port_args is None": "外部没有传入 IPC 端口时，由 engine 自己为 tokenizer/scheduler/detokenizer 分配通信端点。",
    "server_args.node_rank == 0": "多节点部署中只有 rank0 负责启动 engine info bootstrap server，给其他节点同步 scheduler 信息。",
    "server_args.reasoning_parser == \"auto\"": "reasoning parser 自动推断需要在 tokenizer/template 初始化前先解析，避免后续请求阶段才发现 parser 未定。",
    "server_args.node_rank >= 1": "非 0 节点只承载 scheduler/model worker，不启动 tokenizer/detokenizer 和完整 HTTP API。",
    "server_args.tokenizer_worker_num == 1": "单 tokenizer worker 模式下主进程直接持有 TokenizerManager；多 worker 模式改用共享内存和 router。",
    "server_args.enable_metrics": "启用 metrics 时 HTTP 层会注入 Prometheus middleware，scheduler/cache 侧也会带指标 collector。",
    "server_args.ssl_certfile": "提供证书时 uvicorn/granian 走 HTTPS 配置；这里仅记录 SSL 文件，实际监听仍在后续 server backend。",
    "server_args.enable_http2": "HTTP/2 需要 Granian backend；默认 uvicorn 路径只覆盖普通 HTTP/1.1 ASGI 服务。",
    "self.server_args.gc_warning_threshold_secs > 0.0": "只有显式设置 GC 阈值时 tokenizer manager 才打开 GC pause 告警，避免默认日志过多。",
    "server_args.skip_tokenizer_init": "跳过 tokenizer 初始化时 detokenizer 不做 token-id 到文本转换，适用于 embedding/token-id-only 等路径。",
    "self.server_args.tokenizer_worker_num > 1": "多 tokenizer worker 请求必须附带 worker IPC 信息，否则 scheduler 输出无法回到发起请求的 HTTP worker。",
    "self.server_args.language_only": "language-only/EPD encode 请求走 disaggregation encode 旁路，不进入普通 generate decode 流程。",
    "obj.is_single": "单请求直接 tokenize/send/wait；批请求要拆分内部 request state 并复用 batch handler。",
    "obj.return_prompt_token_ids": "用户要求返回 prompt token id 时，tokenization 结果需要暂存在 ReqState 里供最终响应组装。",
    "state is None": "收到的 rid 已不在 `rid_to_state`，通常是请求已 abort/health check 已提前清理，需要避免把孤儿输出写回用户流。",
    "rid.startswith(HEALTH_CHECK_RID_PREFIX)": "health check 请求可能只等任意回包更新时间戳，rid 已清理时静默跳过是预期竞争。",
    "self.enable_metrics": "开启 metrics 时把 scheduler 侧 time_stats 合并进 API meta_info，用户响应才带性能分解。",
    "recv_obj.time_stats is not None": "只有 scheduler 返回了 per-request timing 时，tokenizer manager 才能把它转换成输出 meta_info。",
    "getattr(state.obj, \"return_logprob\", False)": "用户请求 logprob 时，tokenizer manager 需要把 token id/logprob 转成 OpenAI/SGLang API 风格。",
    "not isinstance(recv_obj, BatchEmbeddingOutput)": "embedding 输出没有生成文本 finish 语义，文本生成相关 meta_info 只加到非 embedding 响应。",
    "getattr(server_args, attr) != \"auto\"": "用户显式指定 parser 时不覆盖；只有 auto 才使用 template manager 的推断结果。",
    "suggested is not None": "template manager 成功从 chat template 推断 parser，就把 auto 改写成具体 parser 名称。",
    "self.gracefully_exit": "scheduler 收到优雅退出信号后跳出主循环，不再接收新 batch。",
    "self._engine_paused": "engine pause 时只接收控制消息，不继续组 batch 或调用 model worker。",
    "python/sglang/srt/managers/scheduler.py:batch": "存在可运行 batch 时进入 GPU forward；没有 batch 时进入 idle 维护路径。",
    "envs.SGLANG_ENABLE_STRICT_MEM_CHECK_DURING_BUSY.get()": "调试内存泄漏时在 busy loop 中强制检查 KV pool/radix cache 不变量，生产默认关闭。",
    "self.is_bigram": "bigram 视图下一个逻辑 key 单元对应相邻 token 对，切片需要保留右边界 token 才能组成完整 bigram。",
    "page_size == 1": "page size 为 1 时无需对齐，prefix hit 可以精确到任意 token。",
    "is_eagle and not self.is_bigram": "EAGLE 使用 bigram prefix 语义；第一次进入该路径时把 key 视图切换为 bigram 而不复制 token 数组。",
    "value is not None": "Radix key 变短或变成 bigram 后，KV index/value 必须裁到同样逻辑长度，防止 tree key 与 value 长度不一致。",
    "self.extra_key != other.extra_key": "`extra_key` 不同代表 LoRA/cache salt/隔离域不同，即使 token 相同也不能复用同一段 KV。",
    "self.disable or len(key) == 0": "prefix cache 被禁用或 key 为空时直接返回空命中，scheduler 会按无 cache 路径处理。",
    "len(key) == 0": "page 对齐后可能没有完整 page 可复用，此时不能返回部分 page 的 KV index。",
    "python/sglang/srt/mem_cache/radix_cache.py:value": "radix helper 返回多个节点的 KV span；有命中时需要拼成连续 device index 交给 scheduler。",
    "python/sglang/srt/mem_cache/radix_cache.py:lo < n": "指数搜索还没扫完整个较短 raw token 序列，继续扩大比较窗口。",
    "python/sglang/srt/mem_cache/radix_cache.py:t0[lo:hi] != t1[lo:hi]": "当前窗口内出现第一个分叉；进入二分搜索定位精确分叉点。",
    "python/sglang/srt/mem_cache/radix_cache.py:hi - lo > 1": "分叉窗口长度仍大于 1，需要继续二分缩小到单 token 边界。",
    "python/sglang/srt/mem_cache/radix_cache.py:t0[lo:mid] == t1[lo:mid]": "左半窗口仍完全相同，公共前缀至少延伸到 `mid`。",
    "python/sglang/srt/mem_cache/radix_cache.py:self.is_bigram": "bigram 视图的逻辑单元是相邻 token 对；raw token 匹配数不能直接作为逻辑匹配长度。",
    "self.disable": "禁用 radix cache 时 finished request 的 KV 不进入 tree，需要直接释放 KV slot。",
    "self.disable_finished_insert": "确定性/调试模式可禁止 finished request 写入 radix tree，用于避免 cache 影响复现实验。",
    "is_insert": "只有允许插入时才把 finished request 的 committed KV 提升为可复用 prefix cache。",
    "token_ids is None": "调用方不传 token_ids 时，默认用 prompt + 已生成 token 作为 prefix matching key。",
    "envs.SGLANG_RADIX_FORCE_MISS.get()": "强制 cache miss 的实验开关，用于对比 radix cache 对性能或正确性的影响。",
    "not isinstance(policy, CacheAwarePolicy)": "即使当前排序策略不按 cache 排序，SGLang 也可能预先计算 prefix hit 供后续 load/snapshot 使用。",
    "self.policy == CacheAgnosticPolicy.FCFS": "FCFS 不看 prefix cache；若开启 priority scheduling，只在到达顺序基础上加入用户优先级。",
    "isinstance(policy, CacheAwarePolicy)": "cache-aware policy 会先把 waiting queue 的 prefix 命中写回 Req，再用 LPM/DFS 权重排序。",
    "policy == CacheAwarePolicy.LPM": "LPM 策略优先最长 prefix hit 的请求，让即将进入 prefill 的 batch 更可能复用已有 KV。",
    "policy == CacheAwarePolicy.DFS_WEIGHT": "DFS weight 策略按 radix tree 局部性排序，目标是让相邻请求复用相近 cache 分支。",
    "policy == CacheAgnosticPolicy.LOF": "LOF 关注输出长度而不是 cache hit，适合不想让 prefix cache 影响公平性的策略。",
    "thinking_budget is None": "该请求没有 strict thinking 预算，grammar manager 不需要给 ReasonerGrammarObject 写 budget。",
    "isinstance(req.grammar, ReasonerGrammarObject)": "只有 reasoning grammar 才需要写 `max_think_tokens`；普通 JSON/regex grammar 不消费 thinking budget。",
    "self.grammar_backend is None": "用户请求 structured output 但服务以 `--grammar-backend none` 启动，只能立即 abort 该请求。",
    "req.sampling_params.json_schema is not None": "JSON schema 约束优先生成 grammar cache key，同一 schema 后续请求可复用编译结果。",
    "req.sampling_params.regex is not None": "regex 约束使用 `('regex', pattern)` 作为 cache key，与 JSON/EBNF 编译结果隔离。",
    "req.sampling_params.ebnf is not None": "EBNF 约束使用独立 cache key，避免和 regex/JSON 的 compiled grammar 混用。",
    "req.sampling_params.structural_tag": "structural tag 走同一 grammar cache/Future 管线，但 key 类型与 JSON/regex/EBNF 分开。",
    "not cache_hit": "grammar cache miss 返回 Future，请求必须进入 grammar_queue 等待编译完成。",
    "value": "cache hit 分支里 `value` 已经是可直接挂到 Req 的 grammar object；cache miss 分支里它是后台编译 Future。",
    "self._enable_strict_thinking": "没有显式 structured output 时，strict thinking 仍会初始化 reasoning grammar 来约束思考段 token。",
    "grammar_obj is not None": "strict thinking backend 成功创建 grammar 后，把它挂到 Req，后续 sampling 会应用 token filter。",
    "add_to_grammar_queue": "只有 grammar 编译 Future 未完成的请求才进入 grammar_queue；cache hit 可以直接进 scheduler waiting queue。",
    "i in ready_req_idxs": "同一轮 polling 已判定 ready 的请求不重复检查，避免重复访问 Future 状态。",
    "req.finished() or req.grammar is None": "请求等待 grammar 时可能被 abort；这种请求应从 grammar_queue 移走而不是继续等 Future。",
    "req.grammar.done()": "grammar 编译 Future 完成后，请求可以从 grammar_queue 转回普通 waiting queue。",
    "self.grammar_sync_size == 1": "单 rank 不需要 all-gather，直接使用本地 ready/failed 集合。",
    "logits.device.type in {\"cuda\", \"xpu\", \"musa\"}": "GPU/XPU/MUSA logits 走设备侧 bitmask kernel，避免把 logits 拉回 CPU。",
    "_is_hip": "ROCm/HIP 环境使用 CUDA 兼容实现；非 HIP GPU 默认走 Triton bitmask kernel。",
    "logits.device.type == \"npu\"": "NPU 后端使用 sgl-kernel-npu 注册的 token bitmask op。",
    "s": "xgrammar 找到确定性 jump-forward 字符串时，可以跳过逐 token decode 再 retokenize。",
    "hasattr(tokenizer, \"init_xgrammar\")": "自定义 tokenizer 可以提供专门的 xgrammar 初始化，绕开 Hugging Face TokenizerInfo 转换。",
    "tokenizer_info is None": "自定义 tokenizer 明确表示不支持 xgrammar 时，backend 初始化失败并回退到错误路径。",
    "isinstance(self.kv_cache, MHATokenToKVPool)": "普通 MHA KV cache 使用与 device pool 匹配的 host pool，支持 L2 写回/加载。",
    "isinstance(self.kv_cache, DSATokenToKVPool)": "DSA cache 需要等解析 storage extra_config 后走 hybrid attach，不能在这里直接创建 host pool。",
    "isinstance(self.kv_cache, MLATokenToKVPool)": "MLA KV cache 使用专门 host pool，因为 MLA 的 KV layout 与普通 MHA 不同。",
    "self.scripted_scheduler_hook is not None": "存在脚本化 scheduler hook 时，每个 batch 执行前都给实验代码一个观察/干预点。",
    "self.forward_sleep_time is not None": "调试用人为 sleep，可放大并发/overlap 时序问题，生产路径不应开启。",
    "batch.forward_mode.is_prebuilt()": "prebuilt batch 来自 disaggregation decode 等外部构造路径，scheduler 不再按普通 batch 重新准备输入。",
    "self.is_generation": "生成模型走 token generation forward；embedding/score 等非生成任务会走 run_batch 的其他分支。",
    "self.enable_overlap": "overlap 开启时 CPU 调度和 GPU forward 分离，需要 future_map、stream wait 和状态隔离配合。",
    "not batch.spec_algorithm.is_none()": "speculative batch 需要在 target verify 与 draft extend 之间提前 publish，给 scheduler overlap 留窗口。",
    "batch.spec_algorithm.is_none()": "非 speculative batch 没有 draft 后续工作，model worker 返回后再发布 seq_lens 即可。",
}


ASSIGNMENT_EXPLANATIONS = {
    "tokenizer_manager.max_req_input_len": "scheduler 初始化后回传真实 max input length；tokenizer manager 后续用它做入站长度校验。",
    "app.is_single_tokenizer_mode": "HTTP lifecycle 通过这个标志区分单 tokenizer 与多 tokenizer worker 的 warmup/路由路径。",
    "app.server_args": "single-tokenizer 模式把 server args 挂到 FastAPI app，lifespan/warmup 线程直接读取它。",
    "app.warmup_thread_kwargs": "HTTP server lifespan 会用这些参数执行 warmup，保证监听后模型路径已经完成必要预热。",
    "self._result_dispatcher": "TokenizerManager 的回包分发器；scheduler/detokenizer 返回的控制对象按类型进入对应 handler。",
    "self.sampling_params_class": "请求入站时使用的采样参数实现，后续会把用户 JSON 规范化为内部 SamplingParams。",
    "self.signal_handler_class": "TokenizerManager 使用的信号处理器类型，负责把进程信号转成服务清理动作。",
    "self.recv_from_scheduler": "detokenizer 的输入 IPC socket；scheduler 把 token id/batch output 发到这里。",
    "self.send_to_tokenizer": "detokenizer 的输出 IPC socket；单 tokenizer 模式下文本增量通过它回到 TokenizerManager。",
    "self.tokenizer": "detokenizer 持有 tokenizer 后才能把增量 token id 解码成文本；skip 模式则保持 None。",
    "dp_size": "DP size 决定 routed_dp_rank 是否有效；单 DP 时 routed_dp_rank=0 会被忽略。",
    "tokenized_obj": "单请求完成 tokenizer/chat template/multimodal 处理后的内部请求对象，下一步会通过 IPC 发送给 scheduler。",
    "state.prompt_token_ids": "用户要求回传 prompt token ids 时，把 tokenization 结果挂到 ReqState，最终响应组装会读取它。",
    "recv_obj": "TokenizerManager 从 detokenizer 收到的 batch 输出或控制对象，是 API streaming/non-streaming 回包的来源。",
    "pending_notify": "批量通知暂存表，用于减少逐请求唤醒造成的 event-loop 抖动。",
    "batch_notify_size": "控制一次合并通知多少请求，影响 streaming 高并发下的唤醒粒度。",
    "state": "`rid_to_state` 中的请求等待状态；找到它才能把 scheduler 输出送回对应 API coroutine。",
    "meta_info": "用户响应中的元信息在 tokenizer manager 组装，包含 finish reason、prompt token 数和可选 timing/logprob。",
    "scheduler_time_stats": "scheduler 返回的 per-request 执行耗时，稍后会转换为输出 meta_info。",
    "tokenizer_manager": "主进程中的 TokenizerManager，负责 API 入站、tokenization 和等待 scheduler/detokenizer 回包。",
    "template_manager": "chat/completion 模板管理器，初始化后还会给 auto parser 提供推断结果。",
    "TokenizerManagerClass": "测试或私有 fork 可以替换 TokenizerManager 实现；默认使用标准 TokenizerManager。",
    "self.cur_batch": "scheduler 当前正在执行/准备执行的 batch；abort、pause、metrics 等逻辑会读取它。",
    "self.last_batch": "记录上一轮 batch，overlap/metrics/调试路径会用它理解上一轮执行状态。",
    "recv_reqs": "scheduler 本轮从 tokenizer manager 收到的新请求和控制消息。",
    "python/sglang/srt/managers/scheduler.py:batch": "scheduler 本轮选择出的可执行 batch，可能来自 running decode 或 waiting prefill。",
    "result": "model worker forward/sampling 的输出，下一步必须交给 `process_batch_result` 更新请求和 cache 状态。",
    "self.result_queue": "overlap 调度暂存上一轮 GPU 结果，使 CPU 可以先准备下一轮 batch 再回收上一轮输出。",
    "tmp_batch, tmp_result": "overlap 路径中出队的上一轮结果，必须先 process 后才能安全推进相关请求状态。",
    "disable_overlap_for_batch": "某些 batch 因依赖或特殊 feature 不能 overlap，这个标志决定是否立即处理上一轮结果。",
    "self.token_ids": "RadixKey 持有的 token 序列，是 radix tree 边上的实际匹配内容。",
    "self.extra_key": "RadixKey 的隔离维度；LoRA、cache salt 或租户隔离不同就不能共享 KV。",
    "self.is_bigram": "标记当前 key 是否按 bigram 逻辑解释，主要服务 EAGLE/speculative 路径。",
    "aligned_len": "向下对齐到 page 边界后的可复用 token 数，避免返回半个 KV page。",
    "raw": "bigram 切片需要包含 stop 右侧 token，才能让最后一个 bigram 单元完整。",
    "python/sglang/srt/mem_cache/radix_cache.py:key": "prefix cache 查找/插入使用的 RadixKey；它同时包含 token ids 和 extra_key 隔离域。",
    "python/sglang/srt/mem_cache/radix_cache.py:value": "与 RadixKey 对应的 KV slot indices；tree 命中后 scheduler 会复用这些 device slots。",
    "python/sglang/srt/mem_cache/radix_cache.py:t0, t1": "`match` 直接比较底层 token array，避免把 RadixKey 迭代成 Python 对象列表。",
    "python/sglang/srt/mem_cache/radix_cache.py:n": "两条 key 底层 token 数的较小值，是普通 token 视图下最多可能共享的 raw token 长度。",
    "python/sglang/srt/mem_cache/radix_cache.py:matched_tokens": "先假设 raw token 全部匹配；一旦 galloping search 找到分叉窗口，再回填真实公共前缀长度。",
    "python/sglang/srt/mem_cache/radix_cache.py:190:matched_tokens": "普通 token 视图下，将 raw token 匹配数夹到两个 RadixKey 的逻辑长度内。",
    "python/sglang/srt/mem_cache/radix_cache.py:lo": "当前已确认匹配窗口的左边界；指数搜索和二分搜索都会推进它。",
    "python/sglang/srt/mem_cache/radix_cache.py:step": "指数搜索窗口大小，每轮翻倍，长公共前缀时能用少量 C-level slice compare 跳过大量 token。",
    "python/sglang/srt/mem_cache/radix_cache.py:hi": "本轮比较窗口右边界，限制在 `n` 内，避免越过较短 key。",
    "python/sglang/srt/mem_cache/radix_cache.py:mid": "分叉窗口内的二分切点，用 slice compare 收缩到第一个不同 token。",
    "python/sglang/srt/mem_cache/radix_cache.py:matched": "bigram 模式下 raw token 匹配数要减 1 才是完整 bigram 单元数，再受两个 RadixKey 逻辑长度约束。",
    "prefix_len, last_node": "insert helper 返回已有 prefix 长度和最终节点，调用方据此更新 cache metadata。",
    "kv_committed_len": "请求已经确认可提交的 KV 长度，只有这部分 KV 能进入 prefix cache 或被安全释放。",
    "kv_indices": "req-to-token pool 中的物理 KV slot 索引，把请求 token 位置映射到实际 KV 存储。",
    "radix_key": "finished request 写入 prefix tree 时使用的 key，包含 prompt+output token 和 extra_key 隔离域。",
    "values": "写入 radix tree 的 KV slot index 副本；copy=True 避免后续 req pool 复用时污染 cache metadata。",
    "python/sglang/srt/managers/schedule_policy.py:match_result": "prefix cache 返回的命中摘要，后续会展开到 `Req.prefix_indices/last_node/host_hit_length` 等字段。",
    "self.policy": "调度策略在初始化时会根据 cache 类型做校正，避免选择当前 prefix cache 不支持的策略。",
    "self.tree_cache": "SchedulePolicy 持有 prefix cache 引用，排序前会用它计算 waiting request 的 prefix hit。",
    "self.priority_sign": "priority 排序方向由 `schedule_low_priority_values_first` 决定，统一成乘法符号供 sort key 使用。",
    "self.waiting_queue_radix_tree": "模拟 radix tree 用于 in-batch prefix caching，估计 waiting queue 内部请求之间的共享前缀。",
    "python/sglang/srt/managers/schedule_policy.py:policy": "本轮实际使用的排序策略，队列长度或 cache 能力可能让它不同于用户配置的 policy。",
    "thinking_budget": "从请求参数中取出的 strict thinking token 预算；只有 reasoning grammar 会消费它。",
    "add_to_grammar_queue": "标记该请求是否因为 grammar 编译未完成而暂缓进入 scheduler waiting queue。",
    "python/sglang/srt/constrained/grammar_manager.py:103:key": "JSON schema 请求把 schema 字符串原样作为 payload，后端会走 `dispatch_json -> compile_json_schema`。",
    "python/sglang/srt/constrained/grammar_manager.py:105:key": "regex 请求把正则表达式放入 key，后端会走 `dispatch_regex -> compile_regex`，与 JSON cache 分开。",
    "python/sglang/srt/constrained/grammar_manager.py:107:key": "EBNF 请求进入 `compile_grammar` 路径；key type 让同一文本不会误用 regex/JSON 的 compiled grammar。",
    "python/sglang/srt/constrained/grammar_manager.py:109:key": "structural tag 请求传入序列化后的结构化 tag，xgrammar 后端会先反序列化并兼容 legacy/new format。",
    "python/sglang/srt/constrained/grammar_manager.py:value, cache_hit": "grammar backend 返回 compiled grammar 或 Future；cache_hit 决定请求能否立即进入 waiting queue。",
    "req.grammar": "Req 上的 grammar 字段会被 sampling 路径读取，用于每步填充并应用 token bitmask。",
    "req.grammar_key": "保存 cache miss 时的 grammar key，Future 完成或失败后要用它回写 grammar backend cache。",
    "ready_req_idxs": "本 rank 已完成 grammar 编译或已 abort 的 grammar_queue 索引集合。",
    "failed_req_idxs": "本 rank 轮询超时的 grammar_queue 索引集合，后续会同步到所有 rank。",
    "synced_ready_req_idxs": "多 rank 下取 ready 交集，保证所有 rank 都准备好同一批 grammar 请求后再放行。",
    "synced_failed_req_idxs": "多 rank 下取 failed 并集，只要任一 rank 编译失败/超时，所有 rank 都按失败处理。",
    "return_reqs": "从 grammar_queue 释放出来、准备重新进入 scheduler waiting queue 的请求列表。",
    "self.matcher": "每个请求独享的 xgrammar matcher，记录当前 FSM 状态并生成下一 token mask。",
    "self.ctx": "compiled grammar 上下文可被缓存复用；每个请求复制时会基于它创建新的 matcher 状态。",
    "self.override_stop_tokens": "xgrammar 初始化时从 tokenizer/model EOS 得到的 stop token 覆盖，保证 matcher 终止语义与模型一致。",
    "self.accepted_tokens": "调试和 rollback 用的已接受 token 序列，matcher 拒绝 token 时用于错误上下文。",
    "self.key_string": "保留原始 schema/regex/EBNF 文本，matcher 报错或统计时能定位是哪条约束导致问题。",
    "accepted": "xgrammar matcher 是否接受刚采样出的 token；False 表示约束状态和生成 token 不一致。",
    "matcher": "copy 时重新创建 matcher，保证缓存中的初始 grammar object 不被某个请求的状态污染。",
    "grammar_stats": "grammar cache hit 时复制统计对象并标记 `is_cache_hit=True`，用于 structured output metrics。",
    "self.grammar_compiler": "xgrammar compiler 持有 tokenizer 边界信息，后续把 JSON/regex/EBNF 编译成 matcher 可执行对象。",
    "self.vocab_size": "grammar bitmask 的词表宽度必须与模型 vocab size 一致。",
    "self.override_stop_tokens": "xgrammar 使用模型 EOS/自定义 stop tokens，避免 grammar 终止语义和模型终止语义不一致。",
    "self.any_whitespace": "xgrammar 编译 schema 时的 whitespace 策略，影响 JSON 等格式中空白 token 的可接受性。",
    "self._enable_metrics_flag": "HiCache 是否采集 metrics 的总开关，来自 cache init params。",
    "self.page_size": "HiCache 所有 L1/L2/L3 KV 操作都按 page 对齐，page_size 是 load-back/prefetch 的基本粒度。",
    "self.kv_cache": "当前 GPU device KV pool；HiRadixCache 根据它的具体类型选择 host pool 布局。",
    "self.token_to_kv_pool_host": "HiCache L2 host KV pool，保存从 device 写回或从 L3 预取的 KV page。",
    "self.tp_group": "HiCache 传输和命中查询需要与 TP cache group 对齐，跨 rank 时按这个 group 同步。",
    "self.attn_cp_group": "attention context-parallel cache group，用于 HiCache load-back/prefetch 的跨 rank 同步。",
    "self.attn_tp_group": "attention tensor-parallel cache group，用于 HiCache storage 命中和预取一致性。",
    "self.pp_group": "pipeline-parallel cache group，HiCache controller 需要它处理 PP 场景下的传输协调。",
    "self.enable_storage": "是否启用 L3 storage backend；未配置时 HiCache 只提供 L1/L2。",
    "self.enable_storage_metrics": "只有启用 L3 且 metrics 打开时才采集 storage 相关指标。",
    "extra_config": "L3 storage backend 的解析后配置，会传给 HiCacheController 和 runtime config。",
    "prefetch_threshold": "L3 命中 token 数低于该阈值时放弃预取，避免 I/O 成本超过收益。",
    "prefetch_timeout_config": "L3 预取超时策略配置，用于判断 prefetch 是否应停止等待。",
    "hicache_storage_pass_prefix_keys": "控制是否把 prefix keys 传给 storage backend，供部分 backend 做更精确的 key 查询。",
    "self.is_prefetch_timeout": "当前使用的 prefetch 超时判断函数，默认是线性超时策略。",
    "self.prefetch_stop_policy": "L3 预取停止策略，决定命中不足、超时或资源不足时如何撤销/截断。",
    "self.load_cache_event": "load-back/prefetch 完成通知事件，controller 和 cache 主路径通过它协调异步传输。",
    "self.cache_controller": "HiCache 异步传输控制器，负责 host pool 分配、device<->host copy、storage prefetch 和 ACK。",
    "self.ongoing_write_through": "记录正在写穿到 host/storage 的 radix 节点，避免节点 mutation 与异步写回冲突。",
    "self.ongoing_load_back": "记录正在从 host 加载回 device 的节点片段，避免重复 load-back 同一段 KV。",
    "self.ongoing_prefetch": "按 request id 记录正在进行的 L3->host 预取，terminate/progress 需要这份账本。",
    "self.ongoing_backup": "记录后台 backup 操作，防止驱逐或节点更新时丢失仍在传输的 KV。",
    "self.prefetch_loaded_tokens_by_reqid": "按请求统计实际从 L3 加载的 token 数，用于 metrics 和后续调度判断。",
    "self.work_list": "保存 torch distributed 异步 work 句柄，确保跨 rank HiCache 通信完成后再回收状态。",
    "self.write_through_threshold": "write-through 策略下更积极地写回 host/storage，write-back 策略则用更高阈值减少传输。",
    "self.load_back_threshold": "load-back 最小收益阈值，命中过短时不值得把 host KV 搬回 device。",
    "self.rid": "请求全局 id，是 scheduler 输出回到 TokenizerManager `rid_to_state` 的路由键。",
    "self.origin_input_ids": "原始 prompt token ids；prefix cache、长度校验和 prefill 都以它为基础。",
    "self.origin_input_ids_unpadded": "多模态 padding 前的原始 token ids，用于需要还原用户输入长度的统计或返回。",
    "self.output_ids": "生成阶段 append-only 的输出 token；scheduler 根据长度差推断新增 token，不能原地改写。",
    "self.full_untruncated_fill_ids": "prompt+output 的完整序列镜像，chunked prefill/DLLM 等路径用它恢复 fill 状态。",
    "self.fill_len": "当前已经进入 fill/prefill 处理的 token 长度，admission 不直接截断完整序列。",
    "self.kv_committed_len": "已提交、语义上可保留的 KV 长度；finished/cache 路径只处理这部分 KV。",
    "self.kv_allocated_len": "已经向 KV pool 申请的长度，可能大于 committed 长度，用于处理预分配和回收。",
    "self.kv_committed_freed": "记录 committed KV 是否已释放，防止 abort/finish 多路径重复 free。",
    "self.kv_overallocated_freed": "记录 overallocated KV 是否已释放，避免预分配槽位泄漏或重复释放。",
    "reqs": "ScheduleBatch 中的请求列表；ForwardBatch 会从它派生 LoRA、grammar、position 等 per-request 元数据。",
    "req_to_token_pool": "请求逻辑 token 位置到 KV slot 的映射池，batch 执行和 prefix cache 都会读取它。",
    "token_to_kv_pool_allocator": "物理 KV slot allocator，负责为 extend/decode 分配或释放 KV 存储。",
    "tree_cache": "batch 共享的 prefix cache 引用，finished/unfinished request 会通过它更新 radix cache。",
    "batch_is_full": "标记 running batch 是否已满；为满时可跳过新 prefill 检查，减少 scheduler 热路径开销。",
    "chunked_req": "当前被切块 prefill 的请求，下一轮会继续从它的后续 prompt token 开始。",
    "decoding_reqs": "与 chunked-prefill batch 同时携带的 decode 请求，用于混合 prefill/decode 调度。",
    "req_pool_indices_cpu": "req_pool_indices 的 CPU 镜像，overlap utils 使用；spec draft window 中可能滞后于 GPU tensor。",
    "hicache_consumer_index": "HiCache load-back 与 batch 消费同步用的指针，避免 GPU 在 KV 搬回前读取。",
    "input_ids": "传给 model runner 的本轮输入 token tensor，是 ScheduleBatch 到 ForwardBatch 的核心数据。",
    "prefill_input_ids_cpu": "prefill H2D staging 区，resolve_forward_inputs 会消费它构造最终 GPU input_ids。",
    "mix_running_indices": "混合 prefill/decode 时用于 gather running token 的索引，resolve_forward_inputs 会读取它。",
    "forward_mode": "ForwardBatch 的执行模式，attention backend 依赖它区分 prefill/decode/verify/extend。",
    "batch_size": "本次 forward 的请求数或执行行数，kernel launch 和 sampling batch 都依赖它。",
    "req_pool_indices": "ForwardBatch 中每个请求在 req_to_token_pool 的行索引，attention backend 用它定位历史 KV。",
    "seq_lens": "每个请求当前序列长度，paged attention 和 sampling 都依赖它计算有效上下文。",
    "out_cache_loc": "本轮输出 token 要写入的 KV slot 位置，是 attention 写 KV 的目标地址。",
    "seq_lens_sum": "batch 内总 token 长度，部分 attention backend 用它规划 prefill kernel。",
    "orig_seq_lens": "chunked prefill 前的原始长度，长上下文模型和日志统计需要保留它。",
    "return_logprob": "是否需要返回 logprob；为 True 时 model runner/sampling 会保留额外概率信息。",
    "is_prefill_only": "该 batch 只做 prefill 不采样生成 token，常见于 embedding 或预填充分离路径。",
    "spec_algorithm": "当前 batch 使用的 speculative algorithm，决定 verify/draft worker 和 accept 逻辑。",
    "is_extend_in_batch": "batch 中存在 extend/prefill 请求，attention backend 需要按 extend 而非纯 decode 处理。",
    "batch.forward_iter": "把 scheduler 全局 forward 计数写入 batch，metrics/profile 可用它关联一次 GPU 执行。",
    "future_indices": "overlap/speculative 发布用的 req_pool_indices 快照，worker 执行期间 scheduler 依赖它更新 future_map。",
    "fwd_kwargs": "speculative overlap 时传给 model worker 的 publish hook；非 spec batch 不需要额外 kwargs。",
    "batch_result": "model worker 返回的生成结果，后续 scheduler 会据此更新 token、finish reason、KV cache 和回包。",
}


LINE_EXPLANATIONS = {
    "python/sglang/srt/managers/schedule_policy.py:96": "`tree_cache.match_prefix` 返回的是一次 prefix 查询的完整摘要：GPU device KV 命中、host/HiCache 命中长度，以及 radix tree 节点锚点。",
    "python/sglang/srt/managers/schedule_policy.py:105": "这组解包把 `MatchResult` 写回 `Req`，后续调度排序、KV 分配、HiCache load-back 都从 `Req` 字段读取命中信息。",
    "python/sglang/srt/managers/schedule_policy.py:122": "`_compute_max_prefix_len` 会按请求状态限制最大可复用前缀，避免把不应复用的尾部 token 或特殊边界算进 cache hit。",
    "python/sglang/srt/managers/schedule_policy.py:123": "`num_matched_prefix_tokens` 是 scheduler 视角的总命中长度，把 L1 device 命中和 host 命中合并后再受 `max_len` 截断。",
    "python/sglang/srt/managers/schedule_policy.py:126": "Mamba cache 需要额外记录 branching seqlen；只有对应 cache backend 返回该字段时才写入请求。",
    "python/sglang/srt/managers/schedule_policy.py:128": "HiCache 可能保护某段 cache 不被驱逐；`cache_protected_len` 写入 Req 后会影响后续 cache 管理。",
    "python/sglang/srt/managers/schedule_policy.py:130": "调用方仍拿到完整 `MatchResult`，因为 radix 节点锚点等信息不全都展开在 `Req` 字段里。",
    "python/sglang/srt/constrained/grammar_manager.py:187": "跨 rank structured output 必须在所有 rank 对 ready/failed 达成一致后才能放行，否则各 rank batch 会发散。",
    "python/sglang/srt/constrained/grammar_manager.py:201": "从这里开始把 ready Future 兑现为真正 grammar object，并把请求移回普通 scheduler waiting 路径。",
    "python/sglang/srt/constrained/grammar_manager.py:224": "超时请求也要返回给 scheduler，但它们会带 abort 状态，让上层收到明确失败而不是一直等待。",
    "python/sglang/srt/constrained/grammar_manager.py:237": "最后从 grammar_queue 删除已处理索引，剩余请求继续在后续 scheduler tick 中轮询。",
    "python/sglang/srt/constrained/outlines_jump_forward.py:109": "第一轮只处理字符级确定边；第二轮补 byte-level 边，解决 UTF-8/byte FSM 中不能直接表示成单字符的跳转。",
    "python/sglang/srt/constrained/outlines_jump_forward.py:139": "返回的 map 是 compressed FSM 的核心产物：每个可安全跳过的 state 对应一个确定字符/byte 及下一状态。",
    "python/sglang/srt/constrained/xgrammar_backend.py:79": "采样器选出 token 后会调用这里推进 matcher；下一轮 `fill_vocab_mask` 才会基于新状态计算合法 token。",
    "python/sglang/srt/constrained/xgrammar_backend.py:93": "speculative reject 或 jump-forward retokenize 需要回滚 matcher，`accepted_tokens` 同步截断只用于调试上下文。",
    "python/sglang/srt/constrained/xgrammar_backend.py:105": "这里没有手写 FSM 遍历，而是让 xgrammar matcher 根据当前状态直接填下一 token 的 bitmask。",
    "python/sglang/srt/constrained/xgrammar_backend.py:112": "mask 应用发生在 logits 上，非法 token 会在采样前被置为不可选。",
    "python/sglang/srt/constrained/xgrammar_backend.py:125": "缓存命中时不能复用旧 matcher；这里用同一个 compiled grammar `ctx` 新建 matcher，保证请求状态隔离。",
    "python/sglang/srt/constrained/xgrammar_backend.py:144": "xgrammar 能直接返回确定性字符串时，scheduler 可以尝试 jump-forward，减少逐 token decode。",
    "python/sglang/srt/constrained/xgrammar_backend.py:154": "jump-forward 后文本会重新 tokenization；这段把 matcher 回滚到共同前缀，再接受新 token 序列。",
    "python/sglang/srt/constrained/xgrammar_backend.py:300": "`CompiledGrammar` 是可缓存的静态约束；`GrammarMatcher` 是每个请求运行时状态，二者在这里分开。",
    "python/sglang/srt/constrained/xgrammar_backend.py:317": "GrammarManager 构造 `('json', schema)` key 后会进入这里，最终产物仍是一个 `XGrammarGrammar`。",
    "python/sglang/srt/constrained/xgrammar_backend.py:332": "EBNF 文本直接交给 xgrammar 的 grammar compiler，适合比 JSON schema 更自由的格式约束。",
    "python/sglang/srt/constrained/xgrammar_backend.py:340": "regex 约束在 xgrammar 中编译成 matcher 可执行的 grammar，而不是在 Python 侧逐字符检查。",
    "python/sglang/srt/constrained/xgrammar_backend.py:348": "structural tag 是工具调用/结构化片段的组合约束，需要先解析 JSON 结构再编译。",
    "python/sglang/srt/constrained/xgrammar_backend.py:381": "清空 SGLang grammar cache 时，也要清空 xgrammar compiler 内部 cache，避免旧 schema 编译结果残留。",
    "python/sglang/srt/speculative/spec_registry.py:95": "`create_worker` 是插件 spec algorithm 进入 runtime 的收口点；最终必须返回 scheduler/model runner 可调用的 worker 类。",
    "python/sglang/srt/speculative/spec_registry.py:123": "disaggregation 模式下插件可以构造 draft 阶段输入；默认 None 表示不参与 EPD/PD draft 输入改写。",
    "python/sglang/srt/speculative/base_spec_worker.py:285": "`war_fastpath_runner` 指向最后读取共享 buffer 的 runner，overlap scheduler 的 WAR barrier 会等它的 read-done event。",
    "python/sglang/srt/speculative/base_spec_worker.py:293": "spec v2 可能同时触碰 target/draft 多个 attention backend，scheduler 用这个集合判断是否需要 CPU seq_lens。",
    "python/sglang/srt/speculative/base_spec_worker.py:313": "verify 接受长度回到 CPU 后才触发该 hook，避免 worker 热路径主动制造 GPU->CPU 同步。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1071": "extend/prefill 不是先 draft；target 先处理新 prompt token，并捕获 hidden states 给 draft prefill 用。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1085": "overlap 的 publish 点放在 target prefill 之后、draft prefill 之前，让 scheduler 先看到本轮 seq_lens。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1097": "draft prefill 消费 target hidden states 与 next token，填好 draft KV，并返回下一轮 decode 的 `next_draft_input`。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1123": "adaptive spec 可把 draft 步数降到 0；此时仍走 verify 框架，但只采一个 target bonus token。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1136": "decode 主路径在这里真正生成 draft 树；输出会立刻变成 batch.spec_info 供 target verify 使用。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1139": "`verify` 是 EAGLE decode 的 target 检查阶段，返回 accept_lens、new_seq_lens 和下一轮 draft 输入。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1141": "verify 完成后立即发布 new_seq_lens；后面的 draft_extend 可以和 scheduler 的下一轮准备重叠。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1157": "draft_extend 用 verify 结果更新 draft 侧运行状态，使下一轮 draft 从最新 accepted token 继续。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1441": "verify 的 batch 构造放到 plan stream，尽量和主 compute stream 分离准备 tree mask / positions / out_cache_loc。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1495": "target verify forward 使用的是刚构造好的 verify_forward_batch，而不是原始 scheduler batch。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1525": "采样阶段把 target logits 投影回 draft 树，得到每个请求最终接受的路径和长度。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1532": "Mamba/GDN 状态只提交 accepted path；未接受 draft 分支的状态必须丢弃。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1560": "topk>1 的 accepted path 可能在树中间，需要 compact 到后续 decode 假设的连续前缀位置。",
    "python/sglang/srt/speculative/eagle_worker_v2.py:1573": "`GenerationBatchResult` 是 scheduler 的统一接口；speculative 结果在这里被整理成普通 decode 可消费的形状。",
    "python/sglang/srt/speculative/ngram_worker.py:379": "NGRAM 没有 draft model；这里的 draft 时间统计覆盖 CPU corpus 查询和 batch 改写。",
    "python/sglang/srt/speculative/ngram_worker.py:386": "只有 decode 被改写成 TARGET_VERIFY；extend/prefill 仍然走普通 target forward。",
    "python/sglang/srt/speculative/ngram_worker.py:395": "NGRAM verify 复用 target worker，候选 token 来自 corpus，但正确性仍由 target logits 决定。",
    "python/sglang/srt/speculative/ngram_worker.py:432": "这里复用 EAGLE 的采样工具：输入同样是 verify_input + target logits + 可选 grammar mask。",
    "python/sglang/srt/speculative/ngram_worker.py:451": "接受路径对应的 KV 需要搬到 target cache 的连续位置，后续普通 decode 才能直接接上。",
    "python/sglang/srt/speculative/ngram_worker.py:472": "NGRAM corpus 在 verify 后更新，下一轮检索才能利用刚接受的新 token。",
    "python/sglang/srt/speculative/ngram_worker.py:503": "NGRAM 的下一轮输入只保存 accepted token/length 信息，不携带 EAGLE 所需的 hidden states。",
    "python/sglang/srt/speculative/reject_sampling.py:87": "`AcceptTokenNum` 写入本请求接受的 draft 数，scheduler 后续用它更新 accept_lens 和请求输出。",
    "python/sglang/srt/speculative/reject_sampling.py:89": "最终采样决定 verify 链的下一个真实 token：全接受时从 target 分布采 bonus token，拒绝时从修正残差分布采样。",
    "python/sglang/srt/speculative/reject_sampling.py:156": "最终 token 写回 `Predicts`，位置是最后一个已接受 draft 的全局位置；scheduler 之后像普通 decode 一样消费它。",
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


def _scoped_explanation(
    table: dict[str, str], key: str, path: str, lineno: int
) -> str | None:
    scoped_key = f"{path}:{lineno}:{key}"
    if scoped_key in table:
        return table[scoped_key]
    scoped_key = f"{path}:{key}"
    if scoped_key in table:
        return table[scoped_key]
    return table.get(key)


def _contains_call_name(source: str, name: str) -> bool:
    """Match a call target without treating foo.bar as a prefix of foo.bar_baz."""
    pattern = rf"(?<![\w.]){re.escape(name)}\s*\("
    return re.search(pattern, source) is not None


def _annotation_for_assignment(left: str, right: str, path: str, lineno: int) -> str | None:
    left = left.strip()
    right = right.strip()
    bare_left = left.split(":", 1)[0].strip()
    explanation = _scoped_explanation(ASSIGNMENT_EXPLANATIONS, bare_left, path, lineno)
    if explanation:
        return explanation
    for name, explanation in sorted(
        CALL_EXPLANATIONS.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if name in SUPPRESSED_AUTO_CALL_EXPLANATIONS:
            continue
        if _contains_call_name(right, name):
            return f"`{bare_left}` 接收 `{name}` 的结果：{explanation}"
    return None


def _annotation_for_source_line(path: str, lineno: int, line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith(('"""', "'''")):
        return None
    line_explanation = LINE_EXPLANATIONS.get(f"{path}:{lineno}")
    if line_explanation:
        return line_explanation
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
        return "`RadixKey` 用 `__slots__` 固定 token_ids/extra_key/is_bigram/limit，减少 prefix-cache 热路径对象开销。"
    if stripped.startswith("if "):
        condition = stripped[3:].rstrip(":")
        if condition == "TYPE_CHECKING":
            return "类型检查分支：只给静态类型工具导入重依赖，运行时不会进入这条路径。"
        return _scoped_explanation(BRANCH_EXPLANATIONS, condition, path, lineno)
    if stripped.startswith("elif "):
        condition = stripped[5:].rstrip(":")
        return _scoped_explanation(BRANCH_EXPLANATIONS, condition, path, lineno)
    if stripped.startswith("while "):
        condition = stripped[6:].rstrip(":")
        return _scoped_explanation(BRANCH_EXPLANATIONS, condition, path, lineno)
    if stripped.startswith(("else:", "try:", "except ", "for ")):
        return None

    if re.match(r"^[A-Za-z_][\w\.]*\s*:\s*[^=]+$", stripped):
        name = stripped.split(":", 1)[0].strip()
        return _scoped_explanation(ASSIGNMENT_EXPLANATIONS, name, path, lineno)

    if _is_assignment(stripped):
        left, right = stripped.split("=", 1)
        return _annotation_for_assignment(left, right, path, lineno)

    for name, explanation in sorted(
        CALL_EXPLANATIONS.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if name in SUPPRESSED_AUTO_CALL_EXPLANATIONS:
            continue
        if _contains_call_name(stripped, name):
            return f"关键调用：`{name}` - {explanation}"

    call_match = re.search(r"([A-Za-z_][\w\.]*?)\(", stripped)
    if call_match and not stripped.startswith(("def ", "class ")):
        name = call_match.group(1)
        if name in SUPPRESSED_AUTO_CALL_EXPLANATIONS:
            return None
        return CALL_EXPLANATIONS.get(name)
    return None


def source_block(path: str, start: int, end: int, lang: str = "python") -> str:
    """Return a fenced source excerpt with line numbers.

    Keep excerpts short and purposeful. The surrounding prose should explain why
    the block matters instead of asking readers to infer it from raw code.
    """
    lines = (ROOT / path).read_text().splitlines()
    rendered = []
    seen_annotations: set[str] = set()
    for lineno in range(start, min(end, len(lines)) + 1):
        line = lines[lineno - 1]
        rendered.append(f"{lineno:4d}: {line}")
        annotation = _annotation_for_source_line(path, lineno, line)
        if annotation:
            if annotation in seen_annotations:
                continue
            seen_annotations.add(annotation)
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
                152,
                193,
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
                85,
                130,
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
show_lines("python/sglang/srt/managers/schedule_policy.py", 85, 130)
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
show_lines("python/sglang/srt/managers/scheduler.py", 3178, 3351)
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
                3351,
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
## Grammar object：接口很薄，真正要读实现类

`BaseGrammarObject` 只是采样循环看到的契约：`accept_token` 推进状态，`fill_vocab_mask/apply_vocab_mask` 约束 logits，`rollback` 服务 speculative/jump-forward，`try_jump_forward` 给确定片段加速留接口。

它本身几乎都是 `NotImplementedError`，导读价值有限。真正值得读的是继承类：

- `XGrammarGrammar`：默认 xgrammar 后端的主实现，JSON schema / regex / EBNF / structural tag 最常走这里。
- `GuidanceGrammar`：llguidance 后端实现，用 `LLMatcher` 推进状态。
- `OutlinesGrammar`：outlines/regex 旧路径实现，也承载 compressed FSM jump-forward 的历史设计。
"""
            ),
            code(
                r"""
for path in [
    "python/sglang/srt/constrained/xgrammar_backend.py",
    "python/sglang/srt/constrained/llguidance_backend.py",
    "python/sglang/srt/constrained/outlines_backend.py",
]:
    print("\n==", path)
    for row in find_defs(path):
        if row[2] in {"XGrammarGrammar", "GuidanceGrammar", "OutlinesGrammar"}:
            print(row)
"""
            ),
            guide(
                "`XGrammarGrammar`：BaseGrammarObject 最常见的真实实现",
                "python/sglang/srt/constrained/xgrammar_backend.py",
                59,
                179,
                [
                    "`matcher` 是每个请求独享的 xgrammar 状态机；缓存复用的是 compiled grammar `ctx`，不是共享 matcher。",
                    "`accept_token` 发生在采样之后，若 matcher 拒绝说明 logits mask、retokenize 或 speculative 状态已经失配。",
                    "`fill_vocab_mask -> move_vocab_mask -> apply_vocab_mask` 是每步采样前的 token filter 热路径。",
                    "`copy` 重新创建 matcher，这解释了为什么 grammar cache 能缓存初始对象却不会串请求状态。",
                    "`jump_and_retokenize` 用 rollback + replay 把 jump-forward 后重新分词的 token 序列同步回 matcher。",
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
                89,
                140,
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
                142,
                243,
                [
                    "单机时 ready set 可以直接使用；分布式时 ready 取交集，failed 取并集，偏保守保证各 rank 一致。",
                    "编译超时后会 cancel Future，并把失败对象写入 grammar backend cache。",
                    "这段解释了为什么 structured output 请求有时会先等待 grammar preprocessing，而不是立即进入 scheduler。",
                ],
            ),
            md(
                """
## XGrammar backend：从 tokenizer 到 compiled grammar

`XGrammarGrammarBackend` 负责两件事：

1. 初始化时把 SGLang/Hugging Face tokenizer 转成 xgrammar 的 `TokenizerInfo`，创建 `GrammarCompiler`。
2. 请求到来时按 key type 分发到 JSON schema、regex、EBNF 或 structural tag 编译函数，得到 `CompiledGrammar`，再通过 `_from_context` 包成 `XGrammarGrammar`。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/constrained/xgrammar_backend.py", 188, 245)
show_lines("python/sglang/srt/constrained/xgrammar_backend.py", 300, 379)
"""
            ),
            guide(
                "`XGrammarGrammarBackend.__init__`：tokenizer 信息决定 grammar 能否编译",
                "python/sglang/srt/constrained/xgrammar_backend.py",
                188,
                245,
                [
                    "自定义 tokenizer 可以提供 `init_xgrammar`，否则走 `TokenizerInfo.from_huggingface`。",
                    "`model_eos_token_ids` 作为 stop token 传给 xgrammar，避免 grammar 终止和模型 EOS 语义打架。",
                    "`GrammarCompiler` 是后续 JSON/regex/EBNF/structural tag 编译的共享入口。",
                ],
            ),
            guide(
                "`XGrammarGrammarBackend.dispatch_*`：不同约束如何落到 compiled grammar",
                "python/sglang/srt/constrained/xgrammar_backend.py",
                300,
                379,
                [
                    "`_from_context` 为每个 compiled grammar 创建新的 `GrammarMatcher`，这是请求运行时状态的起点。",
                    "JSON schema 的 `$$ANY$$` 走内建 JSON grammar；普通 schema 走 `compile_json_schema`。",
                    "regex 和 EBNF 分别走 `compile_regex` 和 `compile_grammar`，错误会变成 `InvalidGrammarObject` 并被缓存。",
                    "structural tag 会先兼容 legacy/new format，再调用 `compile_structural_tag`。",
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
                139,
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
show_lines("python/sglang/srt/speculative/spec_registry.py", 24, 130)
show_lines("python/sglang/srt/speculative/spec_info.py", 150, 225)
"""
            ),
            guide(
                "`CustomSpecAlgo`：插件算法必须 duck-type 内建接口",
                "python/sglang/srt/speculative/spec_registry.py",
                24,
                130,
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
## Worker 分层：先看 contract，再看真正闭环

`BaseSpecWorker` 只定义 target/draft worker 的共同 contract；真正的 speculative decode 闭环在具体 worker 的 `forward_batch_generation` 中。

读这部分时优先追三件事：

- 谁产生 draft 候选：EAGLE 是 draft model，NGRAM 是 CPU corpus。
- 谁执行 verify：最终都回到 target worker。
- verify 后如何返回 `GenerationBatchResult`：scheduler 后面只看 accept_lens、new_seq_lens、next_draft_input 等统一字段。
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
        if name in {
            "BaseSpecWorker", "EagleDraftWorkerBase", "EAGLEWorkerV2", "EagleDraftWorker",
            "NGRAMWorker", "draft", "draft_forward", "verify", "forward_batch_generation",
            "_prepare_for_speculative_decoding", "_update_ngram_corpus",
        }:
            print(f"{lineno:4d} {kind:16s} {name}")
"""
            ),
            guide(
                "`BaseSpecWorker`：target worker 和 draft worker 的共同 contract",
                "python/sglang/srt/speculative/base_spec_worker.py",
                274,
                329,
                [
                    "`target_worker` 和 `draft_worker` 是抽象属性；算法可以共享 target runner，也可以有独立 draft runner。",
                    "`resolve_model_worker_batch` 默认按 target batch 解析，复杂算法会覆盖以适配 draft/verify 的 metadata。",
                    "`finalize_after_verify` 是 accept counts 回到 CPU 后的 hook，用于更新 KV 或算法运行时状态。",
                ],
            ),
            guide(
                "`EAGLEWorkerV2.forward_batch_generation`：EAGLE 的主调度闭环",
                "python/sglang/srt/speculative/eagle_worker_v2.py",
                1070,
                1159,
                [
                    "extend/prefill 分支先跑 target，再用 target hidden + next token 做 draft prefill，给下一轮 decode 准备 draft 状态。",
                    "decode 分支先 draft，再把 `EagleVerifyInput` 放回 `batch.spec_info` 交给 target verify。",
                    "`on_publish` 在 target/verify 结束后、draft_extend 前发布 new_seq_lens，是 overlap scheduler 能提前工作的同步点。",
                    "adaptive spec 可以把 `speculative_num_steps` 降到 0，此时构造 trivial verify input 退化成普通 decode。",
                ],
            ),
            md(
                """
### 机制小结：EAGLE draft 如何一次预测多个 token

EAGLE 的 draft 不是让小模型从 prompt 重新自回归一遍，而是复用 target 已经算出的 hidden states 作为起点。prefill/extend 阶段 target 先正常前向，得到 `target_hidden_states` 和 target 采样出的 `next_token_ids`；随后 `draft_extend_for_prefill` 把这些信息喂给 draft model，让 draft KV cache 与当前请求状态对齐。decode 阶段 `EagleDraftWorker.draft_forward` 才能直接从上一轮保存的 `topk_p/topk_index/hidden_states` 继续展开候选。

`draft_forward` 的核心循环是 `for i in range(self.speculative_num_steps)`。第 0 步的输入来自上一轮 target/draft 准备好的 top-k token 与 hidden states；后续每一步都会把上一步 draft model 输出的 logits 归一化，再取 `fast_topk` 或 `fast_sample` 作为下一层候选。也就是说，draft model 仍然按自回归方式一层层预测未来 token，只是这些未来 token 先停在 speculative buffer 里，暂时还没有提交给请求输出。

当 `topk == 1` 时，每个请求每一步只有一个候选，拓扑就是一条链：第 1 个 draft token 的父节点是 bonus/root token，第 2 个 draft token 的父节点是第 1 个 draft token，依此类推。因此代码可以直接拼接 `token_list`，并复用预分配的 `parent_list/top_scores_index`。

当 `topk > 1` 时，候选会形成树。直观地说，第 1 层有 top-k 个 token；第 2 层会从第 1 层的每个候选继续扩展 top-k，于是产生 top-k × top-k 个“父 token -> 子 token”组合；更深层同理。`select_top_k_tokens` 在每一层不仅返回要送入 draft model 的 `input_ids`，还返回 `tree_info`：候选累计分数、候选 token id、以及每个候选对应的父节点位置。循环结束后，`organize_draft_results` 会把多层候选拉平成一批节点，按累计分数选出 `speculative_num_draft_tokens - 1` 个最有希望的节点，再保留父子关系。最后 `build_tree_kernel_efficient` 把这些节点转换成 target verify 所需的 `draft_token`、tree attention mask、`retrieve_index`、`retrieve_next_token` 和 `retrieve_next_sibling`。

因此，EAGLE tree draft 的本质是：draft model 负责提出一棵高概率候选树；树上的每个节点都是“某条候选路径上的下一个 token”；父子边记录这个 token 应该接在哪个历史候选后面。target model 随后会一次性验证这棵树，而不是逐条路径重复前向。
"""
            ),
            guide(
                "`EAGLEWorkerV2.verify`：target 检查 draft 树并产出统一 batch result",
                "python/sglang/srt/speculative/eagle_worker_v2.py",
                1431,
                1584,
                [
                    "`eagle_prepare_for_verify` 把 draft 树转成 target forward batch，包含 tree mask、positions 和 KV 写入位置。",
                    "`target_worker.forward_batch_generation(..., is_verify=True)` 是真正的 target verify forward。",
                    "`eagle_sample` 根据 target logits 决定接受路径，输出 `predict/accept_lens/accept_index`。",
                    "topk>1 的树状 draft 需要把 accepted path compact 到每请求 block 前部，否则后续 chain-layout 代码会读错 KV/hidden。",
                    "返回的 `GenerationBatchResult` 把 speculative 结果伪装成普通 decode 结果，scheduler 后处理可以复用同一套路径。",
                ],
            ),
            md(
                """
### 机制小结：target 如何 verify draft，以及拒绝后如何纠错

verify 的第一步是 `eagle_prepare_for_verify`。它把 draft 阶段产生的树状候选改写成 target model 能一次前向的 batch：`input_ids` 是树中所有候选节点的 token id，`positions` 是这些候选在各自请求中的逻辑位置，`custom_mask` 限制每个节点只能看到原始上下文和自己的祖先节点，`out_cache_loc` 则为 target verify 的临时 KV 写入位置。这样 target model 对整棵 draft 树做一次 forward，就能得到每个候选节点后的 next-token logits。

如果采样配置是全 greedy，`eagle_sample` 会把 target logits 取 `argmax`，再调用 `verify_tree_greedy_func` 沿树检查：当前 draft token 是否等于 target 在父节点处预测的 top-1 token。相等就接受该节点，并沿这个节点继续向下；不相等就停止，当前位置改用 target 的预测 token。树状 draft 的关键在 `retrieve_index/retrieve_next_token/retrieve_next_sibling`：它们告诉 kernel 当前接受节点在扁平 buffer 中的位置、它的第一个孩子在哪里、下一个兄弟在哪里。kernel 不是线性扫完整棵树，而是在树结构中选择一条被 target 认可的路径。

非 greedy 采样下，target logits 会先应用 temperature、top-k、top-p，并在有 grammar 时通过 `vocab_mask` 屏蔽非法 token，然后得到 `target_probs`。如果启用 classic rejection sampling，draft 还必须提供同 vocab 的 `draft_probs`。每个 draft token 的接受概率由 target 概率 `p` 和 draft proposal 概率 `q` 共同决定：代码中的条件是 `coin * q < p`，等价于以 `min(1, p/q)` 的概率接受。target 越相信这个 draft token，越容易接受；draft 高估而 target 低估的 token 会更容易被拒绝。

拒绝并不是简单地“重新跑一遍 decode”。一旦某个 draft token 被拒绝，kernel 会从修正分布 `max(target_probs - draft_probs, 0)` 中采样一个替代 token，写到最后一个已接受节点之后。这就是 speculative sampling 的纠错机制：接受的前缀来自 draft，但第一个不被 target 认可的位置由 target 的残差分布补上，从而保持整体输出分布等价于 target model。若所有 draft token 都被接受，kernel 还会从 target 当前分布中额外采一个 bonus token，因此返回给 scheduler 的 `accept_lens` 是“接受 draft 数 + 1 个 target bonus”。

grammar/structured output 的约束发生在 verify 采样前：`generate_token_bitmask` 生成词表 mask，`apply_vocab_mask` 把非法 token 的 target logits 屏蔽掉。这样非法 draft token 即使出现在候选树里，也不会被 target 的合法分布支持；greedy 路径会因为 target top-1 不匹配而停下，采样路径会因为非法 token 的 target 概率接近 0 而被拒绝，然后由 masked target 分布采出合法替代 token。
"""
            ),
            md(
                """
### 机制深挖：`topk > 1` 时 target 不是验证整棵树是否全对，而是在树里找一条可接受路径

先把关键点说清楚：target model 并不会要求 draft 树上的每个分支都正确。`topk > 1` 的意义是让 draft 在同一层给出多个备选分支；target verify 的任务是在这些兄弟分支中找一个能接上 target 预测/采样结果的孩子，然后沿这个孩子继续向下。如果某一层所有兄弟都接不上，就停止接受，并由 target 自己补出当前位置的 token。

树在 verify 前会被摊平成每个请求一行的 `candidates`。以 `sgl-kernel/tests/speculative/test_eagle_utils.py` 的第一个请求为例：

```text
candidates[0]             = [0, 1, 2, 3, 4, 5]
retrieve_next_token[0]    = [1, 2, -1, 4, 5, -1]
retrieve_next_sibling[0]  = [-1, 3, -1, -1, -1, -1]
retrieve_index[0]         = [0, 1, 2, 3, 4, 5]
```

这四个数组共同表达一棵树：

```text
local node 0: token 0, root/bonus 节点
  child -> local node 1: token 1
    child -> local node 2: token 2
  sibling of local node 1 -> local node 3: token 3
    child -> local node 4: token 4
      child -> local node 5: token 5
```

`retrieve_next_token[i]` 是“第一个孩子”的 local node id；`retrieve_next_sibling[i]` 是“下一个兄弟”的 local node id；`retrieve_index[i]` 是这个 local node 在 target verify 扁平 logits/predict buffer 里的全局行号。注意 local node id 用来走树，global/retrieve index 用来读写 `target_predict`、`predicts`、`accept_index`。

target 一次 forward 这 6 个节点后，会得到 `target_predict` 或 `target_probs`。测试里人为设置了：

```text
target_predict[0, 0] = 3  # target 认为 root 后应该接 token 3
target_predict[0, 3] = 4  # target 认为 node 3 后应该接 token 4
target_predict[0, 4] = 5  # target 认为 node 4 后应该接 token 5
其他位置默认预测 token 18
```

于是 greedy verify 的路径是：

1. 从 root local node 0 开始，先看第一个孩子 local node 1，draft token 是 1。
2. target 在 root 的 logits 行预测 token 3，所以 node 1 不匹配。
3. 沿 `retrieve_next_sibling[1]` 跳到 local node 3，draft token 是 3，匹配 target 的 root 预测，于是接受 node 3。
4. 当前已接受末端变成 node 3；下一层看 node 3 的第一个孩子 local node 4。target 在 node 3 的 logits 行预测 token 4，所以接受 node 4。
5. 再看 node 4 的孩子 local node 5。target 在 node 4 的 logits 行预测 token 5，所以接受 node 5。
6. 最后 `accept_index[0] = [0, 3, 4, 5]`，`accept_token_num[0] = 3`。这里 0 是 root 的全局 index，3/4/5 是被接受 draft 节点的全局 index。

这正是 `VerifyTreeGreedy` C++ kernel 的循环：每一层先 `cur_index = retrieve_next_token[cur_index]` 走到第一个孩子；如果这个孩子 token 不等于 target 当前行的预测，就不断 `cur_index = retrieve_next_sibling[cur_index]` 横向找兄弟；找到匹配的兄弟才写 `predicts[last_accepted_retrieve_idx]`、推进 `accept_index`，并把 `last_accepted_retrieve_idx` 改成这个被接受节点的全局 index。

非 greedy 的 `tree_speculative_sampling_target_only` 也是同一个树遍历骨架，只是“是否接受兄弟节点”的条件从 token id 相等变成概率接受。它会累加同一层已看过兄弟的 target 概率 `prob_acc`，当 `coin <= prob_acc / threshold_acc` 或某个兄弟自己的 `target_prob_single >= threshold_single` 时接受该兄弟；被跳过的兄弟会把 target 概率写进 `draft_probs`，最后从 `relu(target_probs - draft_probs)` 中采样补偿 token。也就是说，tree sampling 仍然是在每一层兄弟集合里挑一条路径，而不是把所有分支都提交。

最后，`EAGLEWorkerV2.verify` 里 `topk > 1` 后还要调用 `_finalize_accept_tree_path`。原因是被接受的路径可能是 `[root, node 3, node 4, node 5]`，并不在每请求 verify block 的前几个连续位置；而后续普通 decode/draft_extend 默认读取“连续链式布局”。所以 `_finalize_accept_tree_path` 会根据 `accept_index` 把接受路径对应的 KV、`predict`、hidden states gather 到每个请求 block 的前部，未接受分支则变成可释放/覆盖的临时 verify KV。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/speculative/eagle_utils.py", 407, 529)
show_lines("sgl-kernel/csrc/speculative/eagle_utils.cu", 275, 312)
show_lines("sgl-kernel/csrc/speculative/speculative_sampling.cuh", 64, 104)
show_lines("sgl-kernel/tests/speculative/test_eagle_utils.py", 8, 84)
"""
            ),
            guide(
                "`NGRAMWorker.forward_batch_generation`：没有 draft model 的 speculative 路径",
                "python/sglang/srt/speculative/ngram_worker.py",
                372,
                521,
                [
                    "`_prepare_for_speculative_decoding` 从 ngram corpus 找候选，并把 batch 改写成 `TARGET_VERIFY`。",
                    "target verify、`eagle_sample`、KV 搬移和 logprob 对齐仍复用 EAGLE 的通用 verify 工具。",
                    "`_update_ngram_corpus` 在 verify 后写入新接受 token，让下一轮 ngram 检索看到最新上下文。",
                    "NGRAM 的 `next_draft_input` 只需要保存 accept_tokens/accept_lens/new_seq_lens，不需要 hidden states 或 draft KV。",
                ],
            ),
            md(
                """
### 机制小结：NGRAM 没有 draft model，draft 输入从哪里来

NGRAM speculative decoding 把“提出候选”这件事从神经网络换成了检索。`NGRAMWorker` 维护一个 `ngram_corpus`，里面记录请求历史中出现过的 token 片段。每轮 decode 前，`_prepare_draft_tokens` 会取当前请求的最近一段上下文作为 query：它把 `origin_input_ids`、已输出的 `output_ids`，以及 overlap 模式下上一轮刚接受但还没写回 `req.output_ids` 的 token 拼起来，再截取最长 `max_trie_depth` 的后缀。

随后 `ngram_corpus.batch_get(req_ids, batch_tokens, total_lens)` 查找这个后缀是否在历史语料中出现过。如果出现过，就把历史中紧随其后的 token 作为 draft token；如果能找到多个延续，返回的 `mask` 会描述这些候选之间的树状关系。这里没有 draft logits、没有 draft hidden states，也没有 draft KV cache；NGRAM 只提供 `draft_token` 和 tree mask，后续仍交给 target verify。

`_prepare_for_speculative_decoding` 会把检索结果拷到 GPU buffer，调用 `reconstruct_indices_from_tree_mask` 生成 `retrieve_index/retrieve_next_token/retrieve_next_sibling/positions`，再把 batch 改成 `ForwardMode.TARGET_VERIFY`。从这一刻开始，NGRAM 和 EAGLE 共用同一套 verify 思路：target 对候选树做前向，`eagle_sample` 决定接受路径，接受后的 KV 被搬到 target cache 的提交位置。

NGRAM 的正确性完全依赖 target verify，而不是依赖 ngram 检索一定准确。检索命中只是“猜测未来 token 可能重复历史片段”；猜错时 target 会拒绝并补出 target 分布下的 token。verify 结束后 `_update_ngram_corpus` 会把本轮接受的 token 写回 corpus，所以 NGRAM 的候选来源会随着请求继续生成而增长。
"""
            ),
            md(
                """
## Accept/reject 的正确性

Greedy verify 可以比较 draft token 与 target top-1；采样场景更复杂，需要 rejection sampling，确保输出分布仍等价于 target model。`reject_sampling.py` 里实现的是接受路径与最终 token 的概率修正。
"""
            ),
            code(
                r"""
show_lines("python/sglang/srt/speculative/reject_sampling.py", 1, 156)
"""
            ),
            guide(
                "`reject_sampling.py`：拒绝采样的核心分支",
                "python/sglang/srt/speculative/reject_sampling.py",
                6,
                156,
                [
                    "kernel 逐步比较 draft token 在 target/draft 概率下是否可接受，接受则推进 `last_accepted_global_idx`。",
                    "一旦拒绝，最终 token 不再直接用 draft，而从修正后的 target-minus-draft 分布采样。",
                    "全部接受时还要采一个 bonus token，这就是 accept_lens 往往包含 bonus 的原因。",
                ],
            ),
            md(
                """
### 机制小结：`speculative_sampling_classic_kernel` 的逐步过程

这个 Triton kernel 处理的是“链式候选”的 classic rejection sampling。grid 的每个 program 对应一个请求；`Candidates[pid, :]` 是该请求的候选 token 序列，`RetriveIndex[pid, :]` 是这些候选在 verify buffer 中对应的全局位置，`TargetProbs[pid, step, vocab]` 是 target verify 后的概率分布，`DraftProbs[pid, step, vocab]` 是 draft proposal 分布。

kernel 先把 root 的全局位置写入 `AcceptIndex`。这里 root 不是一个新生成 token，而是 verify 路径的起点，用来记录后续 token 应该接在哪个全局节点后面。`last_accepted_global_idx` 始终指向当前已接受路径的末端，后面写 `Predicts` 和最终 token 都依赖它定位。

接着进入 verification loop，从 `step = 1` 开始逐个检查 draft token。对当前 draft token，kernel 在 target 分布中取 `p = TargetProbs[..., draft_token]`，在 draft 分布中取 `q = DraftProbs[..., draft_token]`，再读一个均匀随机数 `coin`。如果 `coin * q < p`，这个 token 被接受：`Predicts[last_accepted_global_idx]` 写入该 token，`AcceptIndex` 追加当前节点的全局位置，`num_accept` 加一，并把 `cur_prob_row` 推进到当前 step。否则 verification loop 停止，后续 draft token 全部丢弃。

loop 结束后，`AcceptTokenNum[pid]` 保存接受了多少个 draft token。然后 kernel 必须补一个最终 token。如果所有 draft 都被接受，补 token 直接从 target 当前分布 `p` 中采样，也就是 speculative decoding 常说的 bonus token。如果中途拒绝，补 token 从残差分布 `max(p - q, 0)` 中采样。这个残差分布正是 classic speculative sampling 保持 target 分布不变的关键：draft 已经“占用”了一部分 proposal 概率，拒绝后只能从 target 相对 draft 还缺的那部分概率质量里补。

最后的采样分两遍扫 vocab。第一遍按 block 累加 `norm_sum`，得到目标分布或残差分布的总概率质量；第二遍用 `coin_final * norm_sum` 做 CDF 查找，找到最终 token id，并写入 `Predicts[last_accepted_global_idx]`。因此 kernel 的输出包括三类信息：接受了几个 draft token、接受路径在 verify buffer 中的节点位置、以及每个已接受位置后应该提交给请求的 token。
"""
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

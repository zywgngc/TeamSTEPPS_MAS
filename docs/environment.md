# 环境配置

客户端、语法编译服务和模型服务分别运行。CPU 开发不要求安装 CUDA、vLLM 或所有第三方 MAS 框架。

## 客户端

使用 Python3.12。参考依赖为 httpx0.28.1、jsonschema4.23.0；精确直接依赖在`requirements/client.txt`，完整依赖可在自己的环境另行锁定。`pyproject.toml`提供兼容范围，固定依赖文件用于本项目 CPU 检查。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/client.txt
python -m pip install -e .
python scripts/check_environment.py
```

## MedAgents

TeamSTEPPS使用其招募和终答提示，原生对照另调用其`fully_decode(syn_verif)`。上游源码独立下载至忽略的目录，不重新分发其数据。

```bash
python scripts/bootstrap_upstream.py
python -m pip install -r requirements/native.txt
python -m nltk.downloader punkt punkt_tab
python scripts/check_environment.py --native
```

已有上游克隆可用`--from-local /path/to/MedAgents`导入到新目录；脚本固定至`configs/upstream.json`中的commit，拒绝覆盖已有的不同版本或有改动的目录。另一个已有工作目录可通过`MEDAGENTS_ROOT`配置。NLTK数据可放在`NLTK_DATA`指定的本地目录。

## 模型服务：Linux NVIDIA环境

参考服务版本为vLLM0.24.0，默认模型为Qwen3-8B、non-thinking。此处只提供独立环境的配置，不在开发安装时自动安装CUDA或加载权重；Python、PyTorch、CUDA及驱动组合需适配具体服务器。`requirements/serving.txt`记录vLLM版本，并非全部CUDA依赖的通用锁文件。

```bash
# 在单独的服务环境中执行；先自行选择已分配给自己的GPU。
python -m pip install -r requirements/serving.txt
export MODEL_PATH=/path/to/Qwen3-8B
export GPU_ID=0
CUDA_VISIBLE_DEVICES="$GPU_ID" python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_PATH" --served-model-name qwen3-8b \
  --host 127.0.0.1 --port 8000 \
  --tensor-parallel-size 1 --max-model-len 32768 \
  --max-num-seqs 8 --gpu-memory-utilization 0.70 --enforce-eager
```

模型调用使用`/v1/chat/completions`、`seed`、`chat_template_kwargs.enable_thinking=false`及vLLM的`structured_outputs.grammar`。因此当前合同桥依赖vLLM的结构化输出扩展，不能假定任意兼容聊天接口都能直接替换。[vLLM官方结构化输出说明](https://docs.vllm.ai/en/latest/features/structured_outputs/)。切换backbone或服务版本后应重新验证模板、上下文、截断及语法接口。

## 语法编译服务：独立CPU环境

参考编译器为XGrammar0.2.3；在支持该wheel的Linux环境安装，保持与模型服务的grammar格式相容。此服务不加载模型。可与模型服务共用服务环境，也可在另一环境安装`requirements/grammar.txt`。

```bash
python -m pip install -r requirements/grammar.txt
CUDA_VISIBLE_DEVICES="" python scripts/serve_grammar.py \
  --port 24410 --state-root runs/grammar
```

服务只监听`127.0.0.1`；客户端默认调用`http://127.0.0.1:24410/compile`。远程开发可自行建立端口转发。输出字符串长度约束由收到回复后的逻辑schema验证，结构、枚举与数组约束仍参与编译；API输出上限单独生效。

## 配置与验证范围

```bash
cp .env.example .env
# 按自己的服务地址修改 .env，然后：
source .env
teamstepps-mas --input examples/synthetic_case.jsonl --out runs/example
```

配置项为`MODEL_BASE_URL`、`MODEL_NAME`、`SCHEMA_COMPILER_URL`、`MEDAGENTS_ROOT`和可选`NLTK_DATA`；模型地址也可由CLI覆盖。程序不会读取个人API密钥文件，当前客户端针对本地服务，不包含付费编辑器集成。

也可使用`--config configs/development.json`设置模型、地址、seed、temperature与条件列表。优先级为显式CLI参数、JSON配置、环境变量/内置默认；语法编译地址与上游路径由对应环境变量设置。

CPU场景、导入和dry-run可由CI验证。它们不验证真实模型输出、GPU服务稳定性、端到端医学性能或新机器的CUDA兼容性；真实运行产生的环境锁定、trace和结果保留在本地。

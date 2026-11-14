# Research Atlas · DeepSeek 低成本聊天实验 V0.1

**状态：实验代码。尚未接入网站、未验证真实 DeepSeek 额度/密钥，也不代表私人/团队聊天已上线。**

目标：使用现有 `model_credentials` 加密 Key 验证 DeepSeek `deepseek-flash` 非思考模式下的**单轮连通性、3 轮上下文回忆及 token 消耗**，同时保留未来切换 GPT API 的能力。

## 技术约束

- DeepSeek Chat Completions/Responses API 为无状态接口，**必须由 Research Atlas 本地保存并逐次发送需要的对话历史**；不要复用 OpenAI `conversation_id` 的假设。
- 沿用 `backend/model_vault.py` 的 `load_key(db)`，不向 GitHub Actions、浏览器或日志提交密钥。现有 `backend/model_gateway.py` 专供 JSON 科研抽取，普通文本对话使用独立的 `backend/deepseek_chat_probe.py`。
- 本实验暂不新建生产聊天表、不改 Next.js 页面、不启用复杂记忆和 Skill。后续阶段 P0 私人聊天将使用已确认的 `chat_conversations/chat_messages` 等表和权限校验。
- 测试固定为 `deepseek-flash`，`thinking=disabled`，单轮最多输出 96 tokens（刻意控制消耗）。

## 本地离线测试（不会花模型费用）

```sh
python -m pytest -q tests/test_deepseek_chat_probe.py
```

## 在已配置后端密钥的服务器环境运行

下列指令须在**已有 DATABASE_URL 和 MODEL_VAULT_KEY 的 FastAPI/Worker 环境**中执行；无需重新生成或复制 Key：

```sh
# 不收费：只检查加密 Key 与解密配置是否存在
python -m scripts.deepseek_chat_smoke

# 明确授权：发起 3 次短 DeepSeek API 请求（可能产生费用）
python -m scripts.deepseek_chat_smoke --live
```

输出仅包含成功/失败、轮次、上下文消息数和 tokens，不会打印密钥或原始回答。第一轮记住合成代号 `ATLAS-7Q42`，第二轮回忆，第三轮说明来源；第二轮正确复述且所有请求正常返回即通过。网络失败、余额不足、未配置密钥、解密失败应如实报告。

## 后续推进门槛

1. MockTransport 离线测试通过（依次传递 1/3/5 条对话消息、响应解析、错误不泄露密钥）。
2. 管理员在**实际后端环境**确认 `configured=true`，然后主动执行 `--live`。
3. 真实 API 与上下文通过后，再开始私人聊天持久化、后端 API 路由及 Next.js 页面接入；随后开发团队零调用群聊、`@GPT`/AI 回复。
4. DeepSeek 与 GPT 使用相同内部聊天接口，但模型会话上下文由各自适配层管理；切换 Provider 必须明确处理历史重放和隐私权限。

官方文档：<https://api-docs.deepseek.com/guides/multi_round_chat/>、<https://api-docs.deepseek.com/api/create-chat-completion/>。

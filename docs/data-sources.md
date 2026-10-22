# 数据源核对记录

## GPT-5.1 每日精选升级

2026-10-22 核对 OpenAI 官方 `openai/openai-python` 的 `src/openai/types/responses/response_create_params.py` 与 `web_search_tool_param.py`，确认 Responses 参数中的 `max_tool_calls`、`web_search`、`include=web_search_call.action.sources`。使用固定模型 `gpt-5.1`，结构化结果，联网来源 URL 校验。实现测试使用构造的工具结果，不是实际 API 返回。

当前云机器没有 HOTDESK_OPENAI_API_KEY / OPENAI_API_KEY / HOTDESK_GPT_COST_CNY；无认证只读请求 `api.openai.com/v1/models/gpt-5.1` 遭环境 CONNECT 403。尚未进行实际账户、模型与工具组合联调。Windows DPAPI 亦未在真实 Windows 环境验证。

另核对 [Codex 官方 README](https://github.com/openai/codex#using-codex-with-your-chatgpt-plan)：支持以 ChatGPT 订阅登录 Codex。此授权不是通用 OpenAI API 凭据，Codex 可用模型和工具受当前账户限制；不能据此保证指定 GPT-5.1 的使用权限。

用户随后选择优先使用订阅并接受 Codex 支持的模型。已从官方 npm registry 以 npm 完整性验证安装 `@openai/codex@0.163.0` 至临时检查目录，在 Linux 运行 `exec --help`、`login --help` 核对 `--ignore-user-config`、`--ignore-rules`、`--ephemeral`、`--output-schema`、`--json`、只读沙箱等参数。未执行模型任务、未读取认证文件、未使用云环境登录替代用户登录。

事件结构参考官方 `codex-rs/exec/src/exec_events.rs` 及 `codex-rs/protocol/src/models.rs`：仅接受完成的 `web_search` 事件的结构化 URL 或实际 `open_page` / `find_in_page` URL，与最终 JSON 来源交叉校验。真实 Windows 事件流是否包含足够来源、账户是否有工具权限仍需验证；缺少来源时明确失败，不当作真实热点。

## 原有 TikHub 接口

核对日期：2026-10-22。来源：TikHub 官方 Python SDK 仓库，commit `1ede56bcc53f8c037744cbe2b70c93541b5cf840`。通过现有 HTTPS Git 配置只读获取；未修改项目的 Git remote。

核对文件：`spec/openapi.json`、`src/tikhub/resources/douyin_web.py`、`douyin_search.py`、`xiaohongshu_app_v2.py`。

已核对抖音热榜 GET、抖音综合搜索 POST 的 `publish_time=7` 和小红书搜索 GET 的 `time_filter=一周内`。没有在该版本的 SDK/OpenAPI 中找到小红书全站热榜接口，不能保证其他供应商是否提供。

响应适配测试使用构造样本，不是线上采集快照。当前环境直接访问 `https://api.tikhub.io/openapi.json` 遇到代理 CONNECT 403，未携带密钥。当前机器未设置 TIKHUB_API_KEY、HOTDESK_CALL_COST_CNY、HOTDESK_XHS_HOT_FEED。未发起付费请求，供应商报价未核实。

上线前验证：在平台安全配置密钥及域名许可，依据供应商确认的费用上界配置每次请求费用；分别运行热榜及关键词接口，核实发布时间、链接可达性、分页覆盖和计费。为小红书全站热榜单独选择并验证合法数据源，将标准 JSON feed 接入，不能用其他内容列表替代。

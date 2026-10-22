# 数据源核对记录

核对日期：2026-10-22。来源：TikHub 官方 Python SDK 仓库，commit `1ede56bcc53f8c037744cbe2b70c93541b5cf840`。通过现有 HTTPS Git 配置只读获取；未修改项目的 Git remote。

核对文件：`spec/openapi.json`、`src/tikhub/resources/douyin_web.py`、`douyin_search.py`、`xiaohongshu_app_v2.py`。

已核对抖音热榜 GET、抖音综合搜索 POST 的 `publish_time=7` 和小红书搜索 GET 的 `time_filter=一周内`。没有在该版本的 SDK/OpenAPI 中找到小红书全站热榜接口，不能保证其他供应商是否提供。

响应适配测试使用构造样本，不是线上采集快照。当前环境直接访问 `https://api.tikhub.io/openapi.json` 遇到代理 CONNECT 403，未携带密钥。当前机器未设置 TIKHUB_API_KEY、HOTDESK_CALL_COST_CNY、HOTDESK_XHS_HOT_FEED。未发起付费请求，供应商报价未核实。

上线前验证：在平台安全配置密钥及域名许可，依据供应商确认的费用上界配置每次请求费用；分别运行热榜及关键词接口，核实发布时间、链接可达性、分页覆盖和计费。为小红书全站热榜单独选择并验证合法数据源，将标准 JSON feed 接入，不能用其他内容列表替代。

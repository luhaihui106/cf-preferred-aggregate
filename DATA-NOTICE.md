# 上游数据与使用决策

核查日期：2026-10-29。本项目 MIT 仅覆盖原创代码、测试、工作流及原创文档，不给第三方结果重新授予 MIT。未复制候选项目代码或页面布局；IPDB 在保留并逐轮核对其 MIT 通知的条件下保存完整 CSV 的最小指标记录，其他两个提供方只用小型事实接口。公开可访问不等于许可；缺少根代码 LICENSE 也不能单独证明事实 IP 地址不能引用。以下是有边界的复用决定，不是确定法律结论；权利人异议或新限制出现时应停用并复核。

## 启用：IPDB（1 个提供方、2 个地址族适配器）

- 原始提供方：https://github.com/ymyuuu/IPDB
- 说明：https://github.com/ymyuuu/IPDB/blob/main/README.md
- 仓库 MIT：https://github.com/ymyuuu/IPDB/blob/main/LICENSE ，2025 Mingyu 原文完整保留于 notices/IPDB-LICENSE.txt。
- 选择名单：BestCF/bestcfv4.txt、BestCF/bestcfv6.txt；对应指标：BestCF/ipv4.csv、BestCF/ipv6.csv。
- 每轮解析 main 提交，再从同一不可变提交读取名单、CSV、LICENSE；授权文本改变或名单地址与指标不一致则该源失败。v2 明确分离候选与推荐：完整 CSV 通过地址范围验证进入候选，名单仅作排名注释，严格推荐另按 QUALITY-POLICY.md 门槛过滤。更上游第三方数据权利无法逐项保证。README 的公开资源/开放数据库说明及服务面向非大陆地区用户、禁止恶意使用等条件仍适用；本项目不调用其 API、不解除适用条件。

### 修正 925 条 IPv6 的质量含义

在 b12fec4a489867ffb3192c04ff365b4f5e63636c 及本次 live 读取版本，ipv6.csv 有 925 个唯一地址，各发 4 包；430 条零丢包，317/105/73 条分别丢包 25%/50%/75%；全部下载速度为 0.00 MB/s。CSV 按丢包、平均延迟递增，确有探测指标，不是裸网段枚举，但不能称为 925 条高质量优选或吞吐已验证。零速度不能区分未执行下载、失败或四舍五入。

同提交 bestcfv6.txt 明确发布 10 条，观测上等于 CSV 前 10 条。v1 只导出名单，但上游入榜不能免除质量问题。v2 保存所有已验证 CSV 候选，原始 rank/csv_rank 和 shortlist_rank 分离；严格推荐拒绝正丢包、零速度及证据不足。source.input_rows 是完整表行数，preferred_rows 是独立名单位置数，accepted_rows/rejected_rows 指完整表的地址范围验证。CSV 最多 1000 行，名单最多 20 条，超限失败而非静默截断。

没有发现公开的当前 CSV 测量生成程序。v2 对重复地址保留每一条原始指标观察，不丢弃冲突；推荐采用全部观察通过的保守策略，不择优。旧 select_ipdb 接口仍保留原冲突拒绝测试，但不用于 v2 收集。公开 UpBestIP 工作流只消费名单设置 DNS，不能证明测点、测量时间或重现测量链。平均延迟未标单位，unit=null；MB/s、包数及丢包比例按 CSV 原文保留。每条 measurement_time/probe_viewpoint=null。

## 启用：cf-speed-dns（1 个提供方、1 个适配器）

- 原提供方：https://github.com/ZhiXuanWang/cf-speed-dns
- 文档：https://github.com/ZhiXuanWang/cf-speed-dns/blob/main/README.md
- 实际入口：https://ip.164746.xyz/ipTop10.html

README 明确给出 Top/Top10 IP 接口及 curl 自动获取用法。2026-10-29 本轮普通 User-Agent 直接 GET 200，内容为极小的逗号/换行 IP 结果；Top10 名称不保证有 10 条。历史 403 不代表已停服，也不继续作为禁用理由。没有发现单独数据再分发许可或禁止这种有限事实复用的条款；根 LICENSE 缺失不独立构成禁用理由。

决定仅每轮低频获取文档明确面向消费的最小事实名单、署名并保留入口和顺序，不复制实现、HTML 或完整测量表；这不是宣称得到完整数据库再分发授权，也不提供侵权风险保证。最多 20 条，禁止从错误 HTML 正则捞 IP。不启用 GitHub 镜像回退，不以两条路计两个来源。最小接口没有指标/时间/测点，保持 metrics={} 和 null，不从另一次页面读取拼接不一致测量数据，不赋三网标签。

## 启用：CMLiussss（1 个提供方、3 个分类适配器）

- 提供方及接口/免责声明：https://cf.090227.xyz/
- 实际入口：https://cf.090227.xyz/cmcc 、https://cf.090227.xyz/cu 、https://cf.090227.xyz/ct

首页公开 API 区明确展示接口及配置复用方式。免责声明称仅供参考、不保证准确完整及时、禁止非法用途。此次三个入口普通 GET 均为 200；8/4/6 行是小型 IP#标签名单，不是采集网站全表。没有发现独立的数据开放许可证或禁止该有限事实使用的条款；采用与上述相同的有限、署名、低频事实复用决定，保留授权未知，不借用其他 cmliu 项目的 Apache-2.0 代码许可证。

响应只证明提供方的分类，不证明当前国内运营商测点或独立测量链。carrier_claim 保留 cmcc/cu/ct，carrier_verified=false，输出类别仍为 general；无指标/时间/测点就保持未知。当前 CT 两条 188.164.248.18、188.164.248.143 不在官方标准 CF 网段，必须剔除。Homepage 外部延迟图或资源链接不能证明 IP API 的原始测量来源；这三个分类不是三家独立提供方。

## 未启用及具体原因

### Wetest：明确限制和授权门禁，不采集

条款：https://www.wetest.vip/page/site/terms.html

API 文档：https://www.wetest.vip/page/api/get_cloudflare_ip.html

本轮两页均 200。条款第 2 节禁止自动化大量获取，例外仅为遵守限制的官方 API；第 3 节主张数据汇编等权利。API 文档要求通讯授权 key，示例不是本项目授权，且未明确允许向公开 GitHub 仓库再分发。本项目不调用数据列表/API，不使用文档示例 key，也不通过镜像绕过。

如未来确需该来源，待人工发送的精确问题（本次未发送）：
“能否允许 cf-preferred-aggregate 使用贵方正式授权 API，每小时最多一次抓取 Cloudflare v4/v6 优选结果，并将最小 IP、原始指标、测量时间及来源署名发布到公开 GitHub 仓库，供下游下载？若允许，请明确可公开字段、数量/频率、署名、再分发条件及授权取得方式。”
此许可不是当前三提供方聚合的必需门禁。

### BestCF / joname：不增设聚合转发路线

https://github.com/DustinWin/BestCF/blob/main/.github/workflows/build.yml

https://github.com/joname1/BestCFip/blob/main/collects.py

当前 DustinWin 工作流组合 VPS789、IPDB v4/v6、cf-speed-dns，限量抽取后加来源标签；不能把旧报告所写的 CMLiussss/Wetest 当其当前直接输入。joname 来源更广，含 Wetest，且去重/排序可能损失原顺序或归因。二者不是独立测量提供方。无根 LICENSE 本身并非事实地址不可引用的证明；此处不接入的理由是已可直取合适来源、转发重复和来源限制/归因损失，不是要求每个事实都必须 MIT。没有用聚合路线获取受限 Wetest 数据。

### byoip.top：域名通道，不是数值实测池

https://byoip.top/ 此轮无重定向自动跟随 GET 遇到重定向（并非旧报告的当前 403 结论）。域名可作为另行评估的可选动态域名通道，本任务未实现，不枚举通配符、不把 DNS 解析或 AS13335 归属当优选测量。不为增加来源数量加入域名或中转池。

### CloudflareYes

未启用。已有 IPv6 跨运营商同地址/指标/时间与 NETCUP 重复观察，不足以建立独立国内三网归因；本任务没有把它重新计作三网测量提供方。

## schema v3 默认政策修正（取代上文 v2 的严格默认准入描述）

IPDB 完整 CSV 只作为显式候选保存；默认仅 bestcfv4/bestcfv6 同提交匹配的名单。CMLiussss 及 cf-speed-dns 文档最小优选接口仍启用，来源范围和使用决定未扩大。未知测量时间、测点、缺失指标保留警告，不单独阻断优选；已知正丢包、零速度、非法指标或过期继续排除。level=upstream-preferred/unverified 不是独立验证。冲突明确失败否决，不择优。当前完整规则以 QUALITY-POLICY.md 为准；上文历史样本数量不是当前承诺。

## 计数和范围边界

默认配置 3 个原始提供方、6 个适配器；提供方并不等于经独立核验的测量基础设施。两个 IPDB 地址族及 CML 三类均不可膨胀为独立测点数，额外来源仍可能共享未公开的更上游。逐条 provenance 保留 provider_id、source_id、origin、endpoint_url、rank、指标及未知项；重合仅算一个地址+端口，不用跨测点指标排序。

https://www.cloudflare.com/ips-v4 和 https://www.cloudflare.com/ips-v6 每轮真实获取，仅作官方标准边缘范围校验，不枚举网段造优选。新上游限制或授权变化应人工复核，网络可达性不自动决定权利；IPDB LICENSE 变化有运行时 fail-closed，其余网页条款没有自动语义监控，仍需人工定期复查。

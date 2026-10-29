# CF 公开优选结果聚合

独立、轻量的公开数据仓库：读取上游已经发布的优选结果，校验 Cloudflare 官方边缘网段，保序去重，输出 IPv4 / IPv6 TXT 与逐条来源 JSON。不是测速器，不扫描 CF 网段，不提供代理或订阅，不改任何现有网站或服务器。

当前接入 IPDB、cf-speed-dns、CMLiussss 共 3 个原始提供方 / 6 个适配器。它们不是 6 个独立测点；更上游测量链不完全公开。此前版本 937cee1 仅完成单 IPDB 来源的框架发布，不满足多源端到端验收；该版本 925 条 IPv6 全表也不能等同于高质量优选名单。现在使用 IPDB 明确发布的 shortlist 并关联原始指标，另取两个提供方文档明确提供的最小事实名单。没有地区分组、地区选择器或 GeoIP 请求。

## 直接使用

Raw 基址：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/

- 通用 IPv4：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/general-v4.txt
- 通用 IPv6：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/general-v6.txt
- 全量 IPv4：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/all-v4.txt
- 全量 IPv6：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/all-v6.txt
- 移动：同基址 cmcc-v4.txt / cmcc-v6.txt
- 联通：同基址 cu-v4.txt / cu-v6.txt
- 电信：同基址 ct-v4.txt / ct-v6.txt
- 逐条记录：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/records.json
- 来源状态：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/sources.json
- 刷新状态：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/status.json

三网文件目前有意为空。CMLiussss 的分类作为 carrier_claim 保留，但没有当前国内运营商测点的独立证据，carrier_verified=false；IPDB 和 cf-speed-dns 也不提供可靠的当前运营商测点。所有这些候选仍归 general，不能填进三网文件冒充实测。空文件表示没有符合本项目归因标准的结果，不是下载故障。全量与通用在当前来源配置下相同。

TXT 每行一个标准 IP，无注释。源未提供端口，JSON 的 port 为 null；这不代表已经验证了 443。未来出现明确端口时去重键为地址+端口，TXT 使用 IPv4:port 或 [IPv6]:port；无端口与 443 不被偷偷合并。域名、BYOIP 和反代池不在本项目输出范围内。

## 排序与元数据

固定来源目录顺序为 ipdb-v4、ipdb-v6、cf-speed-dns-v4、cmliussss-cmcc、cmliussss-cu、cmliussss-ct；逐轮取每个来源的下一行，跳过已出现的地址+端口，但保留全部 provenance。每个来源内部的原始 rank、指标字符串和单位保留，不按网络请求完成顺序、随机数或时钟重排。无跨来源统一延迟/速度排行榜。过滤与去重后 rank 可以有空缺；源自身是否有严格质量排序由源决定，本项目只保留其发布顺序。provider_id/origin 表示提供方，endpoint_url 表示实际入口；不把镜像路线计为独立提供方。

- IPDB 下载速度列明确标 MB/s；发送/接收记 packets，丢包率记 ratio。cf-speed-dns/CMLiussss 最小接口未给指标，metrics={}，不从别的时间快照猜测或拼接。
- 平均延迟 CSV 列未标单位，因此 unit=null，不擅自当 ms。
- measurement_time 和 probe_viewpoint 未提供则为 null。
- fetched_at 是本项目成功下载及校验的时间；attempted_at 是本轮开始时间。
- source_revision 是读取的 IPDB Git 提交；source_published_at 是该仓库快照提交时间，不是逐条测量时间，也不一定是该 CSV 最近修改时间。
- fresh 只表示本轮成功抓取，不表示上游刚刚完成测量，更不表示手机端健康。
- carrier_claims 保留上游声称；未验证标签仍归 general，冲突通过 carrier_conflict 明示。

CF 官方网段每轮重新获取：https://www.cloudflare.com/ips-v4 和 https://www.cloudflare.com/ips-v6 。两者任何一个不可用就禁止生成新数据，不凭旧地址或 AS13335 放行。排除私有、保留、非全球单播、不在官方网段的地址。BYOIP 可能属于 CF 网络但不在标准边缘段，本项目有意排除；不收录 bestproxy / proxy 第三方中转。

## 更新、故障与消费约定

GitHub Actions 每小时第 23 分钟请求运行，也支持 Actions → Update preferred results → Run workflow。GitHub 可能延迟或跳过调度，不保证整点或每小时一定换 IP。只在内容变化时普通提交，无 force push / orphan 历史，无 push 触发递归。每轮只保存当前快照，不额外生成历史数据目录；普通 Git 提交仍会积累数据历史。

消费者必须先读取 status.json：检查 usable=true、当前时间不晚于 dataset_valid_until，再按 file_sha256 校验 TXT；多文件来自同一 Git 提交时最可靠。不要只拿裸 TXT 永久缓存。未来 Pages 消费需实现这套约定，此任务不部署 Pages。

- 部分失败：成功源更新，失败源最多保留原成功抓取后 24 小时的数据，source.state=stale；不延长原 fetched_at。过期失败源从新快照移除，三网不会被通用结果补齐。
- 全部源失败：不覆写上次记录/TXT；更新 status.json 与 sources.json 表示 stale / expired。24 小时后 usable=false，旧文件仅保留供排障，不再可消费。没有旧数据就不伪造空的成功数据。
- 官方网段获取失败：不发布新记录，status.state=range_unavailable、usable=false；sources.json 保留上次尝试，当前故障以 status.json 为准。全源失败而旧快照包含当轮官方网段已撤销的地址时，保留文件但标记 range_changed、usable=false。禁止带 scope ID 的 IPv6 地址。
- 先提交失败状态，再由最后一步报告不可用，避免红色工作流掩盖故障状态。但测试失败、生成程序崩溃、GitHub 推送失败无法保证写回；消费者仍须自行判断 valid_until。
- 单请求最大 512000 字节、最多两次尝试、socket 等待最多 10 秒、读取 deadline 25 秒（最后一次阻塞读最多额外 10 秒），禁止重定向。IPDB CSV 最多 1000 行，显式优选名单及其他最小接口最多 20 条；超限失败而非截断。请求串行，工作流总超时 8 分钟，不引入第三方密钥服务。

JSON 顶层 schema_version=1（增加字段兼容）；records.json 内 records 为去重后的记录；status.counts 是对应 TXT 行数，不是原始上游行数。input_rows 是 CSV 或最小接口总行数；preferred_rows 是所读取的上游优选名单行数；accepted_rows 是名单经过地址/范围过滤后的行数，可能含同源重复；rejected_rows 只指名单地址/网段过滤，未入 shortlist 的 CSV 行不算 rejected。rank 为名单顺序，IPDB 额外 csv_rank 保留指标表原顺序。adapter_count/provider_count 是配置数，fresh_provider_count/contributing_provider_count 是本轮成功/参与合并的提供方数；这些不是独立测点计数。

## 来源与使用条件

详见 [DATA-NOTICE.md](DATA-NOTICE.md)，每项区分代码授权、数据条件和测点证据。原始聚合代码为 MIT，不能据此给上游数据重新授权。

默认启用：

- IPDB：https://github.com/ymyuuu/IPDB
- IPv4 名单：https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/bestcfv4.txt
- IPv6 名单：https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/bestcfv6.txt
- 对应指标：https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/ipv4.csv 和 https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/ipv6.csv
- 授权：https://github.com/ymyuuu/IPDB/blob/main/LICENSE
- 条款：https://github.com/ymyuuu/IPDB/blob/main/README.md

读取 IPDB main 的提交 ID 后，实际名单、CSV 和 LICENSE 使用同一不可变提交 URL。每轮核对 LICENSE 与 notices/IPDB-LICENSE.txt；授权文本改变时停止该源的新抓取，须人工复核。原授权文本完整保留。IPDB README 标明数据来自公开资源/开放数据库、服务面向非大陆地区用户；请遵守上游适用范围及当地法规。本项目不调用其 API，不保证上游对每项第三方数据拥有再授权权利。若权利方提出具体异议，应停用相关输入并调查。

- cf-speed-dns：https://github.com/ZhiXuanWang/cf-speed-dns ，文档明确的最小结果接口 https://ip.164746.xyz/ipTop10.html 。
- CMLiussss：说明/免责声明 https://cf.090227.xyz/ ，最小接口 /cmcc、/cu、/ct（全部来源标签保留、运营商测点未证实）。

这两个提供方本次直接 GET 均为 200；此前 403/缺少代码 LICENSE 不足以单独否定最小事实结果复用。决定限量、低频、署名使用公开文档明确供自动获取/配置复用的 IP 结果，不复制代码/页面或完整测量表；独立数据许可证未知，不宣称无限制再分发或法律确定性。其他页面条款没有自动语义监控，须人工复核。

未启用：Wetest 有明确自动化限制，正式 API 授权及公开再分发许可未取得（问题草稿见 DATA-NOTICE，未发送）；BestCF/joname 是转引，当前不需增加重复/限制未清路线；byoip.top 是域名通道，不属数值实测池；CloudflareYes 不足以支持独立三网归因。确切条款、入口、当前检索和范围过滤依据见 DATA-NOTICE，不把镜像计为独立测点。

### 质量与数量不是同一概念

13:16 UTC 本地 live 快照：IPDB v4：CSV 10 → 名单 10 → 接受 10；v6：CSV 925 → 名单 10 → 接受 10。该 IPv6 全表有 495 条丢包记录，全部下载速度为 0；当时名单 10 条零丢包。后续 live 抓取中上游已变为 CSV 68 条，名单仍为 10，但这 10 条全有丢包且速度全为 0。这证明“上游选入”不等于“高质量可用”；本项目不添加未经授权的质量阈值，保留其名单/指标并通过 source.quality_summary 显示名单中非零丢包数、零速度数，零速度原因未知。任何调用方都不应仅凭行数或 fresh 认定质量。

cf-speed-dns 本地接受 1 条；CMLiussss cmcc/cu/ct 分别输入 8/4/6、接受 8/4/4，CT 两条因非官方 CF 边缘段剔除。两轮本地合并后均为 IPv4 27、IPv6 10，3 个提供方成功；这不是未来每轮数量承诺。公开 Actions 最新计数/质量以 status.json 为准。IPv6 目前仍只有 IPDB 一家，不宣称双栈均多源。

## 本地运行与测试

Python 3.10+，只用标准库，无安装依赖。

    python3 -m unittest discover -s tests -v
    python3 pipeline.py --output data
    python3 audit.py

离线测试使用明确的合成 CSV / 网络响应，不拿 fixture 冒充 live。涵盖解析、地址族/网段、重复/顺序/冲突、响应上限、超时、部分/全部故障、过期拒用、确定性和发布边界。实时抓取与 Actions 的结果可查看 data/status.json 与 Actions 日志。

## 限制

这是“公开优选结果的原创聚合实现”，不是原创测速数据、全国最快榜或端点健康保证。不比较不同未知测点的指标，不推断 Anycast 落点，不承诺用户的 ISP 表现或 IPv6 可用性。没有用户管理、UUID、节点凭据或订阅生成。此仓库未使用既有部署工具源码，也不包含生产历史。

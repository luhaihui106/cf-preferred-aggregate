# CF 公开优选结果聚合

独立、轻量的公开数据仓库：读取上游已经发布的优选结果，校验 Cloudflare 官方边缘网段，保序去重，输出 IPv4 / IPv6 TXT 与逐条来源 JSON。不是测速器，不扫描 CF 网段，不提供代理或订阅，不改任何现有网站或服务器。

当前默认仅接入 IPDB 的两个地址族；这是同一上游，不是两份独立测速证据。其他候选的再分发条件不明确时不自动接入。没有地区分组、地区选择器或 GeoIP 请求。

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

三网文件目前有意为空。IPDB 未提供可靠的当前运营商测点，不能把通用数据填进去冒充三网实测。空文件是有效的“没有可信结果”，不是下载故障。全量与通用在当前来源配置下相同。

TXT 每行一个标准 IP，无注释。源未提供端口，JSON 的 port 为 null；这不代表已经验证了 443。未来出现明确端口时去重键为地址+端口，TXT 使用 IPv4:port 或 [IPv6]:port；无端口与 443 不被偷偷合并。域名、BYOIP 和反代池不在本项目输出范围内。

## 排序与元数据

固定来源目录顺序为 ipdb-v4、ipdb-v6；逐轮取每个来源的下一行，跳过已出现的地址+端口，但保留全部 provenance。每个来源内部的原始 rank、指标字符串和单位保留，不按网络请求完成顺序、随机数或时钟重排。无跨来源统一延迟/速度排行榜。过滤与去重后 rank 可以有空缺；源自身是否有严格质量排序由源决定，本项目只保留其发布顺序。

- 下载速度列明确标 MB/s；发送/接收记 packets，丢包率记 ratio。
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
- 单请求最大 512000 字节、最多两次尝试、socket 等待最多 10 秒、读取 deadline 25 秒（最后一次阻塞读最多额外 10 秒），禁止重定向；源最多 1000 行。请求串行，工作流总超时 8 分钟，不引入第三方密钥服务。

JSON 顶层 schema_version=1，records.json 内 records 为去重后的记录；status.counts 是对应 TXT 行数，不是原始上游行数。sources.accepted_rows 是过滤后行数，可能含同源重复；rejected_rows 是因地址/网段校验被剔除的行数。

## 来源与使用条件

详见 [DATA-NOTICE.md](DATA-NOTICE.md)，每项区分代码授权、数据条件和测点证据。原始聚合代码为 MIT，不能据此给上游数据重新授权。

默认启用：

- IPDB：https://github.com/ymyuuu/IPDB
- IPv4：https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/ipv4.csv
- IPv6：https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/ipv6.csv
- 授权：https://github.com/ymyuuu/IPDB/blob/main/LICENSE
- 条款：https://github.com/ymyuuu/IPDB/blob/main/README.md

读取 IPDB main 的提交 ID 后，实际 CSV 和 LICENSE 使用同一不可变提交 URL。每轮核对 LICENSE 与 notices/IPDB-LICENSE.txt；授权文本改变时停止该源的新抓取，须人工复核。原授权文本完整保留。IPDB README 标明数据来自公开资源/开放数据库、服务面向非大陆地区用户；请遵守上游适用范围及当地法规。本项目在 GitHub 发布的是公开仓库 CSV 的聚合，不调用其 API，不保证上游对每项第三方数据拥有再授权权利。若权利方提出具体异议，应停用相关输入并调查。

## 本地运行与测试

Python 3.10+，只用标准库，无安装依赖。

    python3 -m unittest discover -s tests -v
    python3 pipeline.py --output data
    python3 audit.py

离线测试使用明确的合成 CSV / 网络响应，不拿 fixture 冒充 live。涵盖解析、地址族/网段、重复/顺序/冲突、响应上限、超时、部分/全部故障、过期拒用、确定性和发布边界。实时抓取与 Actions 的结果可查看 data/status.json 与 Actions 日志。

## 限制

这是“公开优选结果的原创聚合实现”，不是原创测速数据、全国最快榜或端点健康保证。不比较不同未知测点的指标，不推断 Anycast 落点，不承诺用户的 ISP 表现或 IPv6 可用性。没有用户管理、UUID、节点凭据或订阅生成。此仓库未使用既有部署工具源码，也不包含生产历史。

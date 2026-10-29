# CF 公开优选结果聚合

轻量聚合上游已发布优选结果，剔除已知坏结果，保留来源、排名、指标与未知项，区分默认优选和完整候选。只用 Python 标准库，不测速、不扫描、不生成代理订阅，不改现有 Pages 或服务器。

## 默认政策修正：schema v3

默认 recommended/all/general TXT 和 records.json 使用 upstream-preferred-v1：仅上游公开优选名单且无已知质量排除项。完整候选仍在 candidates 文件。取代 schema v2 的 strict-evidence-v1：未知测点、测量时间或缺失指标改为明确警告，不单独阻断上游优选资格。所有当前结果标为 upstream-preferred/unverified，不是独立代理健康验证。

已知正丢包、零速度、非法/非有限指标、已知过期、来源失败仍排除；缺失指标保持未知而不是零。所有观察的明确失败均可否决端点，不择优掩盖冲突，不把镜像计成独立测量。至少一条观察须来自实际优选名单，不能从完整 CSV 或通用池补数。不设全球统一速度/延迟门槛。完整规则见 [QUALITY-POLICY.md](QUALITY-POLICY.md)。

当前准入/排除数以 [实时 status.json](https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/status.json) 为准：candidate_counts 为候选数，counts 为默认优选数，excluded_records 与 exclusion_reasons 提供排除数量和原因，quality_warnings 提供未知警告（可重叠）。现有来源没有逐行真实测量时间和测点归因，仍可保留其公开优选资格，但不能称为测量健康。坏 IPv6 即使导致默认全空也不会放行。

## 直接使用

Raw 基址：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/

- 推荐 IPv4：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/recommended-v4.txt
- 推荐 IPv6：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/recommended-v6.txt
- 完整候选 IPv4：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/candidates-v4.txt
- 完整候选 IPv6：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/candidates-v6.txt
- 候选及全部来源指标：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/candidates.json
- 推荐及来源：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/records.json
- 来源/状态/机器策略：同基址 sources.json、status.json、policy.json
- all-v4/v6.txt 等价于 recommended-v4/v6.txt，是全部合格端点的去重并集。general-v4/v6.txt 仅含没有上游运营商标注的推荐，不代表验证过的“全国通用”。
- 移动（上游标注，未独立验证）：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/cmcc-v4.txt
- 联通（上游标注，未独立验证）：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/cu-v4.txt
- 电信（上游标注，未独立验证）：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/ct-v4.txt
- 通用（无运营商标注）：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/general-v4.txt
- IPv6 对应文件将 v4 换成 v6；无合格结果时文件为空，不填充。

TXT 每行一个 IP，源未提供端口时 JSON port=null，不表示验证过 443；有端口则 IPv4:port / [IPv6]:port，每个文件按地址+端口去重。CMLiussss 的 carrier_claim/upstream_label 原样保留；cmcc/cu/ct 按上游标注分组，不再因缺乏独立验证而丢弃分类。carrier_verified=false，carrier_grouping=source-claimed/unverified；兼容字段 category=general 不表示 TXT 分类或运营商验证。carrier_claim_sources 给出每个标注的 source_id。冲突端点可同时进入多个被标注文件，carrier_conflict=true，all 仍只计一次。无标注来源不会凭空增加运营商标签；同端点跨源合并保留全部观察，任意明确坏指标会从所有推荐文件一起排除。

status.carrier_export_policy.version=source-claimed-v1 明确当前文件语义；schema 仍为 v3，质量政策 upstream-preferred-v1 不变。三网数量可能重叠，不能相加代替 all。它们不是当地/全国运营商测速保证。

消费者应从同一不可变提交读取 status 与文件：检查 schema_version=3、policy_version、usable=true、当前时间不晚于 recommendation_valid_until，再核对 file_sha256。只下载裸 TXT 无法判断过期。candidate_usable 不代表可推荐；dataset_valid_until 只是候选抓取期限。推荐为空时 usable=false，但完整抓取、正确过滤仍是成功运行。

## 来源、顺序与许可

3 个配置提供方、6 个适配器，不是 6 个独立测点。固定顺序 IPDB v4/v6、cf-speed-dns、CMLiussss cmcc/cu/ct，逐轮取一条，保序去重；每条 provenance 保留所有观察和 quality 警告/排除原因。IPDB 保存完整合法 CSV 候选，rank/csv_rank 是原表顺序，shortlist_rank 标记上游名单位置；先按名单顺序供应优选，再保留非名单候选，后者绝不独立进入默认结果。上游入榜不豁免明确失败。不随机洗牌，不跨未知网络比较速度。

- IPDB：https://github.com/ymyuuu/IPDB 。读取同一不可变提交的 BestCF/ipv4.csv、ipv6.csv、bestcfv4.txt、bestcfv6.txt 与 LICENSE。每轮核对保留的 MIT 通知，变更则停止该源新抓取。下载单位 MB/s，丢包 ratio，延迟单位未明则 null；source_published_at 是提交时间，不是测量时间。
- cf-speed-dns：https://github.com/ZhiXuanWang/cf-speed-dns ，文档最小结果接口 https://ip.164746.xyz/ipTop10.html 。
- CMLiussss：https://cf.090227.xyz/ ，最小公开接口 /cmcc、/cu、/ct；保留来源标签但不冒充独立三网测量。

后两者使用有界、低频、署名的最小事实结果接口，独立数据许可未知，不宣称无限再分发权或法律确定性。原创代码 MIT 不会重新授权上游数据。源条款、原始署名与未启用源决定见 [DATA-NOTICE.md](DATA-NOTICE.md)。Wetest 明确限制批量自动化，未获 API 与再分发许可，不启用；BestCF/joname 镜像不计独立票；byoip 域名、CloudflareYes 和第三方反代池不在本次输入中。

cf-speed-dns 自有首页 https://ip.164746.xyz/ 的确公开每 IP 丢包、速度与时间，本次已评估但未接入伴随指标。首页与 Top 是两个独立缓存响应；即便 IP 相同，也不能证明是同轮测量，且页面时间没有时区。为避免把另轮同 IP 指标冒充当前 Top 快照，本版本继续只收 Top 原序，metrics={}，measurement_time=null，明确 unknown 警告；不声称已过滤其网页所列指标。可进一步考虑同一不可变上游提交匹配，但不为本次最小分类修复扩展采集路径。

## 新鲜度与失败

fetched_at 是成功下载/校验结束时间；measurement_time 未提供就为 null，绝不以 fetch/commit 代替。每轮获取 https://www.cloudflare.com/ips-v4 与 https://www.cloudflare.com/ips-v6 ，仅全球单播且在官方网段的地址进入候选；域名、BYOIP、保留/私有地址排除。

部分失败源候选最多保留原抓取后 24 小时，不续期；过期移出当前合并，缓存观察不可推荐。全源或官方网段失败，推荐立即清空，旧候选和 last-good-candidates.json 留作取证；过期绝不 usable。last-good 只在所有配置源成功时更新，历史 Git 提交也保留。采集 state 与 recommendation_state 分开显示 upstream-preferred/empty/degraded/expired，不用 healthy 暗示认证健康。

Actions 每小时第 23 分钟请求运行，支持手动触发；GitHub 可能延迟/跳过。调度、并发锁、最小权限与固定 action SHA 保留。只提交变化，不 force push，不额外堆积历史目录。先写故障状态，再使全源故障工作流失败；推荐空但采集成功不报失败。测试崩溃/推送失败无法保证状态写回，消费端仍须检查截止时间。

单响应上限 512000 字节、最多两次尝试、socket 最多 10 秒、读取 deadline 25 秒（阻塞读可能额外 10 秒）；拒重定向；CSV 最多 1000 行，最小名单最多 20 条；串行有界抓取，工作流超时 8 分钟，无额外依赖或数据库。

## 本地验证

Python 3.10+：

    python3 -m unittest discover -s tests -v
    python3 pipeline.py --output data
    python3 audit.py

离线合成 fixture 不冒充实时结果。测试覆盖坏 IPv6、正速度但测量时间未知、非有限/缺失指标、冲突、时效边界、全源/部分失败、无填充输出、计数与哈希及发布边界。实际抓取见 Actions 和 status.json。

这不是全国最快榜、Anycast 落点或手机 ISP 性能保证。没有身份/传输/运行时认证证据，authenticated_proxy_health 始终 not tested；即使推荐通过也不意味着真实代理认证成功。私人认证验证是独立后续工作，不在公共 CI 中执行。无地区分组、GeoIP 或自主地区测速。

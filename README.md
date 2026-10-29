# CF 公开候选与严格推荐

轻量聚合公开结果：校验 Cloudflare 官方网段，保留来源、排名、指标，区分完整候选和严格推荐。只用 Python 标准库，不测速、不扫描、不生成代理订阅，不改现有 Pages 或服务器。

## 宁缺毋滥：v2 消费语义变更

旧版 all/general TXT 和 records.json 只是地址合法的候选。schema_version=2 起，它们只输出通过 strict-evidence-v1 的推荐；完整候选移到明确的 candidates 文件。默认推荐可能全部为空，不回退、不凑数。旧消费者需要明确选择推荐或候选，不能假定旧文件仍有原数量。

推荐最低证据：零丢包且有一致的包计数、正且有限的 MB/s 下载速度、24 小时内真实测量时间、可归因的测点/网络背景、本轮成功抓取且未过期。缺失、未知、非有限、负数、正丢包、零速度、陈旧或来源失败分别记录原因。同端点所有观察必须通过，不择优掩盖冲突，不把镜像计成独立测量。不要求明确城市，但需要可信测点背景；不设全球统一速度/延迟门槛。完整规则与状态定义见 [QUALITY-POLICY.md](QUALITY-POLICY.md)。

当前准入/排除数以 [实时 status.json](https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/status.json) 为准：candidate_counts 为候选数，counts 为推荐数，excluded_records 与 exclusion_reasons 提供排除数量和原因（原因可以重叠）。现有来源未提供逐行真实测量时间及测点归因，按此策略不能称为测量健康；零推荐是正常失败关闭，不是靠候选补齐的理由。

## 直接使用

Raw 基址：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/

- 推荐 IPv4：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/recommended-v4.txt
- 推荐 IPv6：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/recommended-v6.txt
- 完整候选 IPv4：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/candidates-v4.txt
- 完整候选 IPv6：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/candidates-v6.txt
- 候选及全部来源指标：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/candidates.json
- 推荐及来源：https://raw.githubusercontent.com/luhaihui106/cf-preferred-aggregate/main/data/records.json
- 来源/状态/机器策略：同基址 sources.json、status.json、policy.json
- all-v4/v6.txt 等价于 recommended-v4/v6.txt；general-v4/v6.txt 只取验证分类为 general 的推荐。cmcc/cu/ct-v4/v6.txt 为已验证的运营商推荐，不能从通用候选填充。

TXT 每行一个 IP，源未提供端口时 JSON port=null，不表示验证过 443；有端口则 IPv4:port / [IPv6]:port，地址+端口去重。CMLiussss 标签保存在 carrier_claim/upstream_label，验证分类仍 general，carrier_verified=false，因此三网推荐文件有意为空。

消费者应从同一不可变提交读取 status 与文件：检查 schema_version=2、policy_version、usable=true、当前时间不晚于 recommendation_valid_until，再核对 file_sha256。只下载裸 TXT 无法判断过期。candidate_usable 不代表可推荐；dataset_valid_until 只是候选抓取期限。推荐为空时 usable=false，但完整抓取、正确过滤仍是成功运行。

## 来源、顺序与许可

3 个配置提供方、6 个适配器，不是 6 个独立测点。固定顺序 IPDB v4/v6、cf-speed-dns、CMLiussss cmcc/cu/ct，逐轮取一条，保序去重；每条 provenance 保留所有观察和各自 quality 原因。IPDB 保存完整已验证 CSV，rank/csv_rank 是原表顺序，shortlist_rank 标记上游名单位置；上游入榜也不豁免质量门槛。不随机洗牌，不跨未知网络比较速度。

- IPDB：https://github.com/ymyuuu/IPDB 。读取同一不可变提交的 BestCF/ipv4.csv、ipv6.csv、bestcfv4.txt、bestcfv6.txt 与 LICENSE。每轮核对保留的 MIT 通知，变更则停止该源新抓取。下载单位 MB/s，丢包 ratio，延迟单位未明则 null；source_published_at 是提交时间，不是测量时间。
- cf-speed-dns：https://github.com/ZhiXuanWang/cf-speed-dns ，文档最小结果接口 https://ip.164746.xyz/ipTop10.html 。
- CMLiussss：https://cf.090227.xyz/ ，最小公开接口 /cmcc、/cu、/ct；保留来源标签但不冒充独立三网测量。

后两者使用有界、低频、署名的最小事实结果接口，独立数据许可未知，不宣称无限再分发权或法律确定性。原创代码 MIT 不会重新授权上游数据。源条款、原始署名与未启用源决定见 [DATA-NOTICE.md](DATA-NOTICE.md)。Wetest 明确限制批量自动化，未获 API 与再分发许可，不启用；BestCF/joname 镜像不计独立票；byoip 域名、CloudflareYes 和第三方反代池不在本次输入中。

## 新鲜度与失败

fetched_at 是成功下载/校验结束时间；measurement_time 未提供就为 null，绝不以 fetch/commit 代替。每轮获取 https://www.cloudflare.com/ips-v4 与 https://www.cloudflare.com/ips-v6 ，仅全球单播且在官方网段的地址进入候选；域名、BYOIP、保留/私有地址排除。

部分失败源候选最多保留原抓取后 24 小时，不续期；过期移出当前合并，缓存观察不可推荐。全源或官方网段失败，推荐立即清空，旧候选和 last-good-candidates.json 留作取证；过期绝不 usable。last-good 只在所有配置源成功时更新，历史 Git 提交也保留。采集 state 与 recommendation_state 分开显示 healthy/empty/degraded/expired，healthy 只指公开证据合格，不是认证代理健康。

Actions 每小时第 23 分钟请求运行，支持手动触发；GitHub 可能延迟/跳过。调度、并发锁、最小权限与固定 action SHA 保留。只提交变化，不 force push，不额外堆积历史目录。先写故障状态，再使全源故障工作流失败；推荐空但采集成功不报失败。测试崩溃/推送失败无法保证状态写回，消费端仍须检查截止时间。

单响应上限 512000 字节、最多两次尝试、socket 最多 10 秒、读取 deadline 25 秒（阻塞读可能额外 10 秒）；拒重定向；CSV 最多 1000 行，最小名单最多 20 条；串行有界抓取，工作流超时 8 分钟，无额外依赖或数据库。

## 本地验证

Python 3.10+：

    python3 -m unittest discover -s tests -v
    python3 pipeline.py --output data
    python3 audit.py

离线合成 fixture 不冒充实时结果。测试覆盖坏 IPv6、正速度但测量时间未知、非有限/缺失指标、冲突、时效边界、全源/部分失败、无填充输出、计数与哈希及发布边界。实际抓取见 Actions 和 status.json。

这不是全国最快榜、Anycast 落点或手机 ISP 性能保证。没有身份/传输/运行时认证证据，authenticated_proxy_health 始终 not tested；即使推荐通过也不意味着真实代理认证成功。私人认证验证是独立后续工作，不在公共 CI 中执行。无地区分组、GeoIP 或自主地区测速。

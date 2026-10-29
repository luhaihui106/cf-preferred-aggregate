# 公开优选聚合策略 upstream-preferred-v1

schema_version=3。默认 recommended/all/general TXT 与 records.json 表示“上游已发布优选，剔除已知坏结果”，不是独立验证健康、全国最快或手机测速榜。此版本取代 strict-evidence-v1 将未知测点/测量时间当默认阻断的规则。

## 默认资格

- 必须有实际上游优选名单依据。IPDB 仅同一不可变提交的 bestcfv4/bestcfv6 与 CSV 匹配的地址；不能把完整 CSV 升级成默认优选。CMLiussss 文档公开优选接口及 cf-speed-dns Top 接口是公开优选依据。
- 地址、地址族、全球单播、当轮 Cloudflare 官方网段校验不变。无端口时 port=null，不推定测过 443。
- 上游未提供 measurement_time、probe_viewpoint 或指标，保持 null/空指标与 unknown_* warnings，不捏造时间、不当成零或失败。缺失时间/测点不阻断上游优选资格。
- 已提供指标必须有效：有限非负数；loss ratio 在 [0,1]、必须为零；download_speed 单位 MB/s，必须大于零；包计数若提供必须为非负整数，两个计数均有时 sent>0 且 received=sent。已知正丢包、零速度、非有限/畸形/负数、错误已声明单位均排除。缺指标仅警告，延迟单位未明保留 null，不猜测单位或跨网络排名。
- 已提供测量时间必须带时区、非未来且年龄不超过 86400 秒；已知过期 valid_until 排除。未知测量时间无测量健康期限承诺。
- 来源须本轮 fresh，fetched_at 非未来且不超过 86400 秒。抓取新鲜不表示测量健康。

## 冲突、顺序与计数

同端点 address+port 的全部观察保留。任意观察的明确失败/过期/来源非 fresh 否决端点，至少一条观察须有上游优选依据；不择优隐藏失败，不多数投票，镜像不算独立测量。仅缺指标/上下文不是否决票。原 CSV 非名单行可作候选与冲突观察，但不能独立供应默认优选。

候选以固定来源目录逐轮取一条合并。IPDB 先按 shortlist_rank 供应入榜行，再按 csv_rank 保存非入榜候选；rank/csv_rank 原表序号不改。默认记录过滤候选后保持此顺序，不随机、不比较跨测点速度。

每条 provenance.quality 和 record.quality 提供 level、eligible、warnings、reasons；level 为 upstream-preferred/unverified 或 candidate/unverified。含上游优选观察但被排除的端点仍保留其来源资格标签，eligible=false 及 reasons 才表示排除。任何当前记录均不成为 independently proxy verified；authenticated_proxy_health='not tested'。

status.counts 是默认输出计数；candidate_counts 是完整合法候选计数。excluded_records 按去重端点计数；exclusion_reasons 和 quality_warnings 按端点计数；observation_exclusion_reasons 按观察计数；原因可重叠。sources.accepted_rows 是合法候选观察数，preferred_rows 是上游名单位置数，recommended_observations 是源内通过观察数，default_eligible_records 是实际进入默认输出且该源有合格优选观察的端点数。跨源端点会重叠，不能相加当联合数量。recommended_provider_count 是实际供应默认结果的提供方数，不是独立探针数。

## 新鲜度与失败（保留既有安全行为）

state 是采集状态 fresh/partial/stale/expired/range_unavailable/range_changed。recommendation_state 为 upstream-preferred/empty/degraded/expired，不使用 healthy 暗示健康。usable 只表示有默认合格结果，collection_ok 表示本轮有成功供应源且官方范围有效。推荐空本身不是采集失败。

部分失败来源候选最多保留原 fetched_at 后 24 小时，不续期，不能推荐。过期移出供应池；同端点若仍有其他源供应，保留失败源旧观察作否决，直到该源刷新。全源/官方范围故障立即清空默认结果，保留候选和 last-good 取证，不伪装可用。last-good-candidates.json 仅所有配置源均成功时更新。

消费者应从同一不可变提交读取 status 和数据，检查 schema_version=3、policy_version、usable、当前时间不晚于 recommendation_valid_until，再核对 file_sha256。推荐期限取抓取期限及已知测量/显式期限的最早值；未知测量时间不捏造期限。candidate_usable/dataset_valid_until 不代表健康。裸 TXT 本身没有时效保证。

无填充、无地区/运营商已验证保证、无代理身份测试。carrier_claim 为上游声称；cmcc/cu/ct 文件按该标注导出，明确“上游标注，未独立验证”，carrier_verified=false。general 仅无上游三网标注，all 为全部合格端点去重并集；冲突可进入多个被标注文件，保留 carrier_conflict 和 carrier_claim_sources，不能把分类数量相加当独立端点。category=general 是兼容的非验证字段，不再决定 TXT 分组。未知来源不推断标注，明确坏指标跨所有分组否决。status.carrier_export_policy.version=source-claimed-v1 标记此语义，质量政策未变。原始候选不是默认优选。来源许可、范围与调度不扩大，本次不恢复已取消的 Pages 集成。

# 严格公开证据策略 strict-evidence-v1

宁缺毋滥。候选合法不等于质量合格；抓取成功不等于测量新鲜。本项目不做测速或代理认证。机器策略见 data/policy.json，JSON schema_version=2。

## 推荐门槛（所有条件同时成立）

1. 地址是标准全球单播，属于当轮成功获取的 Cloudflare 官方网段。仅候选通过这一层不够。
2. 同一地址+端口的每条来源观察都通过以下证据门槛；不是选最好的一条，也不是多数投票。
3. loss 是有限数、单位 ratio、范围 [0,1]，必须等于 0。正丢包 positive_loss；负数/大于 1 为 invalid_loss；缺失、NaN、Infinity 为 unknown_loss。零丢包还必须有有限整数 packets 计数、sent>0 且 received=sent；否则 invalid_packet_evidence。一次以上样本仍不代表统计可靠性保证。
4. download_speed 是有限数、明确 MB/s、严格大于 0。0 为 zero_speed，负数 invalid_speed，缺失/非有限 unknown_speed。不混用 Mbps、MB/s，不猜测延迟单位。不设全球统一速度/延迟及格线，正速度只是最低证据，不宣称最快。
5. measurement_time 必须是带时区的真实测量时间，相对本轮完成时间年龄在 [0,86400] 秒（端点含边界）。缺失/无时区/不可解析为 unknown_measurement_time，未来 future_measurement_time，超期 stale_measurement_time。提交时间、网页发布时间、抓取时间均不可替代。
6. probe_viewpoint 必须是上游明确提供、可归因的非空测点/网络背景描述，不能是 unknown/n/a/none/null/-。不硬性要求城市：可信探针标识+明确网络背景也可以。现有适配器未获得逐行关联的测点证据，一律 null；不能靠标签、IP GeoIP 或本聚合服务器所在地补写。以后接入新测点字段必须先审查其归因契约，任意字符串本身不是可信证据。
7. 本轮该来源 state=fresh 且观察 fetched_at 年龄同样为 [0,86400] 秒。缓存回退、失败、过期观察不能推荐；即使它原本速度为正也不例外。

unknown_*_unit 区分单位不足；source_not_fresh 区分源失败。每条 provenance.quality 保留自身原因，record.quality 是原因并集；status.exclusion_reasons 按去重端点计数，observation_exclusion_reasons 按观察计数。同一记录可以有多个原因，因此原因相加不等于排除总数。不会因上游 shortlist 豁免，也绝不补齐默认文件。

## 候选、冲突和归因

IPDB 完整 CSV 经过地址/官方网段校验进入 candidates.json（最多 1000 行，超限拒绝而非截断）；rank/csv_rank 保留 CSV 原始行序，shortlist_rank 单独记录同提交 bestcfv4/v6 名单位置，未上榜为 null。重复地址的所有指标观察均保留；冲突不抹去、不择优。旧 select_ipdb 解析接口仍测试，但发布器使用完整候选收集接口。

其他提供方的有界最小名单全部保留。固定目录顺序 round-robin 合并，只按地址+端口去重；每源 rank 不洗牌，不跨测点排名。provider_id 是提供方而非独立测量票数；镜像不是独立票，本策略不投票。carrier_claim/upstream_label 是来源声称，category 是验证后分类；没有可验证运营商测点时只归 general，三网空着，不推定已验证三网健康。

JSON 的 port=null 表示源未声明端口，不表示验证了 443。没有身份、Host/SNI、传输、运行时认证证据，所有记录 authenticated_proxy_health='not tested'。推荐也只表示公开证据通过本策略，绝不是手机网络或真实代理健康保证。

## 新鲜度、失败与消费

- status.state 是采集层 fresh / partial / stale / expired / range_unavailable / range_changed。
- recommendation_state=healthy 表示采集完整且有合格公开证据；empty 表示完整抓取但零合格；degraded 表示部分失败/网段不可获取/全源失败或有推荐但采集降级；expired 表示已过期或网段撤销。healthy 不代表认证健康。
- counts 是默认推荐 TXT 的计数，candidate_counts 是候选 TXT 计数。usable 只表示推荐非空；collection_ok 表示本轮有成功贡献源且取得官方网段，推荐空不使工作流失败。全源或官方网段故障先写回失败状态，再令 Actions 失败。
- 每轮官方网段重新获取，不用陈旧网段放行。部分源失败，候选最多回退至原 fetched_at+24h，不延长；过期源从当前部分合并移除。全源失败保留当前候选用于取证，candidate_usable 仅在未过期且官方网段仍有效时成立，默认推荐立刻清空。网段失败默认推荐也立刻清空。
- 部分源过期时，不再独立供应当前候选；但若同端点仍由其他源供应，保留失败源的旧观察作否决证据，直到该源成功刷新，不能通过“坏报告过期消失”把冲突端点升级为推荐。
- last-good-candidates.json 只在所有配置源成功时替换；降级/过期不覆盖它，取证文件不宣称可用。Git 普通历史保留旧证据，不创建无限历史目录。
- 消费者必须同一不可变提交读取 status 和文件，检查 schema_version/policy_version、usable、当前时间<=recommendation_valid_until、当轮 file_sha256；不能只永久缓存裸 TXT。recommendation_valid_until 取所有入选观察测量/抓取期限最早值，无推荐则 null。dataset_valid_until 仅是候选抓取截止，不可用于替代测量期限。
- 源时钟不可信、没有测量时间或测点时，宁可推荐为空。当前数目与逐源原因只能以实时 status.json 为准，不静态承诺数量。

## v1 → v2 迁移

这是明确的消费语义变更：旧 all/general/三网 TXT 和 records.json 从“地址合法候选”改成“严格推荐”；新 candidates-v4/v6.txt 与 candidates.json 明确提供完整候选，不能当默认推荐。recommended-v4/v6.txt 是 all-v4/v6.txt 的等价便捷入口。空文件是有效的失败关闭结果，不会回填候选。status.counts 不再代表候选数量，旧消费者需显式选择迁移语义。本仓库不修改生产 Pages。

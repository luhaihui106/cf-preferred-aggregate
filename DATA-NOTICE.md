# 上游数据与授权说明

本项目 LICENSE 只授予原创 Python、测试、工作流和本项目撰写文档的 MIT 权利，不把第三方测量结果重新授予 MIT。地址、数值和来源信息保留上游身份；授权依据与剩余未知分别列出，不把“公开可访问”等同于自由再分发。

核查日期：2026-10-29。下表是默认来源决策，未启用项目不会被运行时请求，也不通过镜像绕过限制。

## 启用：ymyuuu/IPDB

- 仓库 https://github.com/ymyuuu/IPDB ，本次审阅版本 4148f0e981ce640ebec8fa68f4c7bb8211ff2b2a。
- 原始数据位于 BestCF/ipv4.csv、BestCF/ipv6.csv；不是原始 CF CIDR 目录，不使用 bestproxy。
- 仓库根 LICENSE 为 MIT，版权 2025 Mingyu，未见对仓库 CSV 的单独排除；完整文本见 notices/IPDB-LICENSE.txt。启用依据是该公开仓库整体 MIT 声明和这些随仓库发布的 CSV，不是仅凭代码 license 推断任何外部 API 数据都能复用。
- README 的服务说明称数据来自公开资源/开放数据库、服务仅面向非大陆地区用户、不允许恶意使用。不调用其 API；本项目不承诺能解除上游限制。
- 没有独立的测量数据库授权文本，也无法逐条核实其更上游原始数据权属。当前决定是保留明确仓库授权及原声明、有限转引该仓库 CSV，不能保证第三方权利或代替法律意见；如条款改变或出现异议，停止对应来源并复核。
- 指标及测点：当前 CSV 含包数、丢包率、平均延迟、下载速度 (MB/s)，无逐条测量时间、测点 ISP/地点。一般候选，不得贴国内三网实测标签。Git 提交时间只作快照发布信息。

## 未启用的候选

### ZhiXuanWang/cf-speed-dns / ip.164746.xyz

https://github.com/ZhiXuanWang/cf-speed-dns 、https://ip.164746.xyz/ 。当前仓库含 index.html 表格和 ipTop.html / ipTop10.html 结果文件，README 提供获取接口；网站本次返回 HTTP 403，已通过 GitHub 检查发布页格式，未绕过站点访问限制。未发现根 LICENSE，README 的使用接口说明不是明确的批量再分发许可；故默认不启用、不复制代码或页面。历史作者测点自述不能证明当前 ISP。需要数据再分发授权后再接入。

### CMLiussss

https://cf.090227.xyz/ 与 https://cf.090227.xyz/cmcc 、https://cf.090227.xyz/cu 、https://cf.090227.xyz/ct 。本次直接访问 403；先前公开格式为 IP#标签，未知当前响应体与测量链，接口名不能独立证明 ISP。未建立当前数据批量再分发许可，不启用。代码许可证即使存在，也不自动覆盖站点结果。

### Wetest

https://www.wetest.vip/page/site/about.html 、https://www.wetest.vip/page/api/get_cloudflare_ip.html 、https://www.wetest.vip/page/site/terms.html 。已检查公开介绍和服务条款。条款第 2 节禁止用自动化工具大量获取数据，除非通过其 API 并遵守使用限制；第 3 节主张数据汇编等知识产权，未给出本项目所需的再分发授权。数据可能混合自有监测及第三方来源。页面/API 有三网与指标，但批量抓取/再分发受限；本项目没有获得许可。不调用 bulk API、不采集列表、不借 BestCF 转引绕开限制。关于页可访问不代表授权。需要明确许可范围后才评估。

### BestCF 镜像/聚合

https://github.com/DustinWin/BestCF 、https://github.com/joname1/BestCFip 。检查其公开 README / 仓库信息。它们是上游结果的聚合/转引，不是新增独立测点。DustinWin 的来源链包括 IPDB、CMLiussss、Wetest 等；聚合项目自身的授权不能消除原数据限制，因此不用它们为未知授权源提供后门。本次无需镜像回退，避免重复计为独立验证。

### byoip.top

https://byoip.top/ 本次直接访问 403；这是动态域名候选而非保证可输出的数值 IP 池。未建立数据再分发许可；不启用、不枚举通配符、不把任意 *. 域名当地址。即使解析为 AS13335，也未必在本项目允许的 CF 标准边缘网段内。

### CloudflareYes

不启用。既有观察中 IPv6 三网存在同地址、指标、时间与 NETCUP 节点重复，不能作为三份国内 ISP 证据。没有可信的独立三网来源时保持三网 TXT 为空；不把 general 静默填充进去。

## CF 官方网段

https://www.cloudflare.com/ips-v4 、https://www.cloudflare.com/ips-v6 仅作为官方标准边缘范围校验依据，不把其中的所有地址枚举成“优选”。保存当轮网络段以便审计；每次新发布必须真实获取，不缓存无限延期。

> NOTE: Legacy monitor scripts were removed. Use unified launcher run_crawl.sh creator_outreach to run and monitor tasks.

# B绔欑淇℃壒閲忓彂閫佸伐鍏?

鑷姩鍖栨壒閲忓彂閫丅绔欑淇★紝鏀寔骞跺彂鍙戦€併€佹暟鎹簱璁板綍銆佸幓閲嶇瓑鍔熻兘銆?

## 馃搧 鏂囦欢缁撴瀯

```
bilibili_dm_sender/
鈹溾攢鈹€ openclaw_creators.csv          # 鍗氫富鏁版嵁锛?01浣嶏級
鈹溾攢鈹€ send_bilibili_dm_manual.py     # 涓诲彂閫佽剼鏈紙甯︽暟鎹簱璁板綍锛夆瓙
鈹溾攢鈹€ dm_record_store.py             # 鏁版嵁搴撳瓨鍌ㄦā鍧?
鈹溾攢鈹€ schema.sql                     # 鏁版嵁搴撹〃缁撴瀯
鈹溾攢鈹€ check_dm_status.py             # 妫€鏌ュ彂閫佺姸鎬?
鈹溾攢鈹€ run_crawl.sh creator_outreach            # 瀹炴椂鐩戞帶鑴氭湰
鈹溾攢鈹€ start.sh             # 鍚姩鑴氭湰
鈹斺攢鈹€ README.md                      # 鏈枃妗?
```

## 馃殌 蹇€熷紑濮?

### 1. 瀹夎渚濊禆

```bash
pip install playwright supabase
playwright install chromium
```

### 2. 閰嶇疆鏁版嵁搴?

鍦?Supabase SQL Editor 涓墽琛?`schema.sql` 鍒涘缓琛細

```sql
-- 鎵ц schema.sql 涓殑鎵€鏈塖QL璇彞
```

### 3. 閰嶇疆鐜鍙橀噺

纭繚 `config/base_config.py` 涓厤缃簡锛?

```python
SUPABASE_URL = "your_supabase_url"
SUPABASE_KEY = "your_supabase_key"
```

### 4. 杩愯鍙戦€佽剼鏈?

```bash
cd /Users/sunminghao/Desktop/MediaCrawler/bilibili_dm_sender
./start.sh
```

鎴栫洿鎺ヨ繍琛岋細

```bash
python3 send_bilibili_dm_manual.py
```

## 馃搳 鏁版嵁搴撹〃缁撴瀯

### `bilibili_dm_records` 琛?

| 瀛楁 | 绫诲瀷 | 璇存槑 |
|------|------|------|
| id | BIGSERIAL | 涓婚敭 |
| user_id | TEXT | B绔欑敤鎴稩D |
| username | TEXT | 鐢ㄦ埛鍚?|
| message | TEXT | 鍙戦€佺殑娑堟伅鍐呭 |
| status | TEXT | 鍙戦€佺姸鎬?(success/failed) |
| error_msg | TEXT | 閿欒淇℃伅锛堝け璐ユ椂锛?|
| sent_at | TIMESTAMP | 鍙戦€佹椂闂?|
| campaign | TEXT | 娲诲姩鏍囪瘑 (openclaw_2026) |
| created_at | TIMESTAMP | 鍒涘缓鏃堕棿 |

**鍞竴绾︽潫**: `(user_id, campaign, status)` - 鍚屼竴娲诲姩涓瘡涓敤鎴峰彧鑳芥湁涓€鏉℃垚鍔熻褰?

## 馃攳 鏌ヨ缁熻

### 鏌ョ湅鎴愬姛鍙戦€佹暟閲?

```sql
SELECT campaign, COUNT(*) as success_count
FROM bilibili_dm_records
WHERE status = 'success'
GROUP BY campaign;
```

### 鏌ョ湅澶辫触璁板綍

```sql
SELECT username, error_msg, sent_at
FROM bilibili_dm_records
WHERE status = 'failed'
ORDER BY sent_at DESC;
```

### 鏌ョ湅浠婂ぉ鍙戦€佺殑璁板綍

```sql
SELECT username, status, sent_at
FROM bilibili_dm_records
WHERE DATE(sent_at) = CURRENT_DATE
ORDER BY sent_at DESC;
```

## 馃洜锔?鍔熻兘鐗规€?

### 鉁?宸插疄鐜?

1. **骞跺彂鍙戦€?*: 5涓爣绛鹃〉鍚屾椂鍙戦€侊紝鏁堢巼鎻愬崌5鍊?
2. **鏁版嵁搴撹褰?*: 鑷姩璁板綍姣忔潯绉佷俊鐨勫彂閫佺姸鎬?
3. **鍘婚噸鏈哄埗**: 鑷姩璺宠繃宸叉垚鍔熷彂閫佺殑鐢ㄦ埛
4. **鍙嶈嚜鍔ㄥ寲妫€娴?*: 闅愯棌webdriver鐗瑰緛
5. **瀹炴椂杩涘害**: 鏄剧ず鍙戦€佽繘搴﹀拰缁熻淇℃伅
6. **閿欒澶勭悊**: 璁板綍澶辫触鍘熷洜锛屼究浜庢帓鏌?
7. **鎵规寤惰繜**: 閬垮厤瑙﹀彂骞冲彴闄愬埗

### 馃摑 绉佷俊鏂囨

```
hihi浣犲ソ鍛€锛屾姳姝夋墦鎵板暒锛屾垜鏄寳浜腑鍏虫潙瀛﹂櫌鐨勭爺绌跺憳锛岀湅鍒颁綘涓婚〉鍒嗕韩浜嗗緢澶歄penclaw鐨勮惤鍦板簲鐢紝鎯抽個璇蜂綘鍙傚姞鎴戜滑涓惧姙鐨勯緳铏惧ぇ璧涳紝鍩烘湰淇℃伅濡備笅锛?

涓叧鏉戝闄㈡鍦ㄥ姙鐨?OpenClaw"姣旇禌馃幆锛屽垎瀛︽湳榫欒櫨銆佺敓浜у姏榫欒櫨鍜岀敓娲婚緳铏句笁鏉¤禌閬擄紝鏍稿績鏄湅璋佺殑"铏?瑙ｅ喅瀹為檯闂鑳藉姏鏇村己銆傚叏鍦烘渶浣冲閲?0涓?100浜縏oken锛屾瘡鏉¤禌閬撹繕鍚勬湁10涓幏濂栧悕棰濓紝鎴鏃ユ湡3鏈?9鏃?3锛?9锛岃繕鏈夋渶鍚庝袱澶╂椂闂?

鎶ュ悕涔熷緢绠€鍗曪細涓婁紶涓摼鎺ヨ娓呮浣犵殑铏捐兘鍋氫粈涔堝氨琛岋紝涓嶇敤浜や唬鐮侊紝鏍稿績鐪嬪疄闄呭簲鐢ㄦ晥鏋滐紝濡傛灉缁撳悎纭欢浼氶澶栧姞鍒?

鎶ュ悕閾炬帴锛歨ttps://claw.lab.bza.edu.cn

璇︾粏淇℃伅鍙互鐪嬭繖鏉¤繛鎺ワ細https://mp.weixin.qq.com/s/RfqXfunmEP1NLIln-9YUvQ
```

## 馃搱 浣跨敤娴佺▼

1. **鍚姩鑴氭湰** 鈫?娴忚鍣ㄨ嚜鍔ㄦ墦寮€
2. **鎵嬪姩鐧诲綍** 鈫?鍦ㄦ祻瑙堝櫒涓櫥褰旴绔?
3. **鎸夊洖杞︾户缁?* 鈫?鑴氭湰寮€濮嬭嚜鍔ㄥ彂閫?
4. **骞跺彂鍙戦€?* 鈫?5涓爣绛鹃〉鍚屾椂宸ヤ綔
5. **鑷姩璁板綍** 鈫?姣忔潯娑堟伅閮借褰曞埌鏁版嵁搴?
6. **瀹屾垚缁熻** 鈫?鏄剧ず鎴愬姛/澶辫触鏁伴噺

## 馃敡 宸ュ叿鑴氭湰

### 妫€鏌ュ彂閫佺姸鎬?

```bash
python3 check_dm_status.py
```

浠庢祻瑙堝櫒浼氳瘽涓粺璁′粖澶╁彂閫佺殑绉佷俊鏁伴噺銆?

### 瀹炴椂鐩戞帶

```bash
python3 run_crawl.sh creator_outreach
```

瀹炴椂鏄剧ず鍙戦€佽繘搴﹀拰缁熻淇℃伅銆?

### 鏌ヨ鏁版嵁搴?

```bash
python3 dm_record_store.py
```

鏌ヨ鏁版嵁搴撲腑鐨勫彂閫佽褰曞拰缁熻淇℃伅銆?

## 鈿狅笍 娉ㄦ剰浜嬮」

1. **鐧诲綍鐘舵€?*: 棣栨杩愯闇€瑕佹墜鍔ㄧ櫥褰曪紝涔嬪悗浼氫繚鎸佺櫥褰曠姸鎬?
2. **鍙戦€侀檺鍒?*: B绔欏彲鑳芥湁绉佷俊棰戠巼闄愬埗锛岃剼鏈凡娣诲姞寤惰繜閬垮厤瑙﹀彂
3. **鏁版嵁搴撻厤缃?*: 纭繚Supabase閰嶇疆姝ｇ‘锛屽惁鍒欐棤娉曡褰曟暟鎹?
4. **鍘婚噸鍔熻兘**: 閲嶅杩愯鑴氭湰浼氳嚜鍔ㄨ烦杩囧凡鍙戦€佺殑鐢ㄦ埛
5. **閿欒澶勭悊**: 澶辫触鐨勬秷鎭細璁板綍鍒版暟鎹簱锛屽彲浠ュ悗缁噸璇?

## 馃搳 鎬ц兘鎸囨爣

- **鎬荤敤鎴锋暟**: 201浣嶅崥涓?
- **骞跺彂鏁?*: 5涓爣绛鹃〉
- **棰勮鏃堕棿**: 6-8鍒嗛挓
- **鎴愬姛鐜?*: 鍙栧喅浜庣綉缁滃拰骞冲彴闄愬埗

## 馃悰 鏁呴殰鎺掓煡

### 闂1: 鎵句笉鍒拌緭鍏ユ

**鍘熷洜**: B绔欓〉闈㈢粨鏋勫彉鍖?
**瑙ｅ喅**: 妫€鏌ラ〉闈㈠厓绱狅紝鏇存柊閫夋嫨鍣?

### 闂2: 鏁版嵁搴撹繛鎺ュけ璐?

**鍘熷洜**: Supabase閰嶇疆閿欒
**瑙ｅ喅**: 妫€鏌?`config/base_config.py` 涓殑閰嶇疆

### 闂3: 鍙戦€佸け璐?

**鍘熷洜**: 缃戠粶闂鎴栧钩鍙伴檺鍒?
**瑙ｅ喅**: 鏌ョ湅鏁版嵁搴撲腑鐨?`error_msg` 瀛楁

## 馃摑 鏇存柊鏃ュ織

### v3.0 (2026-03-17)

- 鉁?娣诲姞鏁版嵁搴撹褰曞姛鑳?
- 鉁?瀹炵幇鍘婚噸鏈哄埗
- 鉁?浼樺寲閿欒澶勭悊
- 鉁?鏇存柊绉佷俊鏂囨
- 鉁?鍒涘缓瀹屾暣鏂囨。

### v2.0 (2026-03-17)
- 鉁?娣诲姞骞跺彂鍙戦€佸姛鑳斤紙5涓爣绛鹃〉锛?
- 鉁?娣诲姞鍙嶈嚜鍔ㄥ寲妫€娴?
- 鉁?鏀逛负鐩存帴璁块棶绉佷俊椤甸潰
- 鉁?浼樺寲閫夋嫨鍣ㄥ尮閰?
- 鉁?娣诲姞鎵嬪姩纭鐧诲綍

### v1.0 (2026-03-17)
- 鉁?鍩虹涓茶鍙戦€佸姛鑳?
- 鉁?鑷姩鐧诲綍妫€娴?

## 馃摓 鑱旂郴鏂瑰紡

濡傛湁闂锛岃鑱旂郴椤圭洰缁存姢鑰呫€?

## 馃搫 璁稿彲璇存槑

鏈伐鍏蜂粎渚涘涔犲拰鐮旂┒浣跨敤锛屼娇鐢ㄨ€呴渶閬靛畧B绔欑敤鎴峰崗璁拰鐩稿叧娉曞緥娉曡銆?



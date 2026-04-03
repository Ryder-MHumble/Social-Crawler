> NOTE: Unified launcher is now run_crawl.sh / run_crawl.ps1 / run_crawl.cmd. See tasks/README.md.

# MediaCrawler 鈥?绀句氦濯掍綋鑸嗘儏閲囬泦绯荤粺

鍩轰簬 Playwright + CDP 鐨勫骞冲彴绀句氦濯掍綋鍐呭鐖彇妗嗘灦锛屽綋鍓嶉厤缃敤浜庣洃娴?*涓叧鏉戜汉宸ユ櫤鑳界爺绌堕櫌**鍜?*鍖椾含涓叧鏉戝闄?*鐨勭浉鍏宠垎鎯咃紝鏁版嵁缁熶竴瀛樺偍鑷?Supabase锛圥ostgreSQL锛夈€?

---


## 鏀寔骞冲彴

| 骞冲彴 | 浠ｇ爜 | 鍐呭 | 涓€绾ц瘎璁?| 浜岀骇璇勮 | 鍒涗綔鑰?|
| ---- | ---- | ---- | -------- | -------- | ------ |
| 灏忕孩涔?| `xhs` | 鉁?绗旇 | 鉁?| 鉁?| 鉁?|
| 鎶栭煶 | `dy` | 鉁?瑙嗛 | 鉁?| 鉁?| 鉁?|
| B 绔?| `bili` | 鉁?瑙嗛 | 鉁?| 鉁?| 鉁咃紙鍚姩鎬?绮変笣鍏崇郴锛?|
| 寰崥 | `wb` | 鉁?甯栧瓙 | 鉁?| 鉁?| 鉁?|
| 蹇墜 | `ks` | 鉁?瑙嗛 | 鉁?| 鉁?| 鉁?|
| 璐村惂 | `tieba` | 鉁?甯栧瓙 | 鉁?| 鉁?| 鉁?|
| 鐭ヤ箮 | `zhihu` | 鉁?鍥炵瓟/鏂囩珷 | 鉁?| 鉁?| 鉁?|

褰撳墠榛樿鐖彇锛氬皬绾功銆佹姈闊炽€丅绔欍€佸井鍗氾紙瑙?[run_crawl.sh](run_crawl.sh#L33)锛夈€?

---


## 鏍稿績鑳藉姏

### 1. 鐪熷疄娴忚鍣ㄩ┍鍔紙鍙嶆娴嬶級

閫氳繃 **CDP锛圕hrome DevTools Protocol锛?* 鐩存帴鎺ョ鐢ㄦ埛鏈満宸插畨瑁呯殑 Chrome锛岃€岄潪妯℃嫙娴忚鍣細

- 浣跨敤鐢ㄦ埛鐪熷疄鐨勬祻瑙堝櫒鎸囩汗銆佹墿灞曘€佸巻鍙茶褰?
- 鐧诲綍鐘舵€佹寔涔呬繚瀛橈紙`browser_data/` 鐩綍锛夛紝Cookie 闀挎湡鏈夋晥
- `AUTO_CLOSE_BROWSER = False`锛氱埇瀹屼笉鍏虫祻瑙堝櫒锛孋ookie 涓嶅け鏁?

### 2. 鍏抽敭璇嶆悳绱?+ 鐩稿叧鎬ц繃婊?

鐖彇娴佺▼锛氬钩鍙板叧閿瘝鎼滅储 鈫?鐩稿叧鎬ц繃婊?鈫?淇濆瓨鑷?Supabase

褰撳墠鍏抽敭璇嶏紙[run_crawl.sh:30](run_crawl.sh#L30)锛夛細

```text
涓叧鏉戜汉宸ユ櫤鑳界爺绌堕櫌, 鍖椾含涓叧鏉戝闄? 涓叧鏉戝闄?
```

鐩稿叧鎬ц繃婊わ紙[base_config.py:34](config/base_config.py#L34)锛夛細鍙繚瀛樺唴瀹逛腑瀹為檯鍑虹幇浠ヤ笅璇嶈涔嬩竴鐨勭粨鏋滐紝閬垮厤骞冲彴妯＄硦鎼滅储甯︽潵鐨勬棤鍏虫暟鎹細

```python
RELEVANCE_MUST_CONTAIN = [
    "涓叧鏉戜汉宸ユ櫤鑳界爺绌堕櫌",
    "涓叧鏉戝闄?,
    "鍖椾含涓叧鏉戝闄?,
    "涓叧鏉慉I鐮旂┒闄?,
]
```

### 3. 鏁版嵁鍘婚噸

- **璺ㄦ杩愯鍘婚噸**锛氭瘡娆″惎鍔ㄦ椂浠?Supabase 棰勫姞杞藉凡瀛樺湪鐨?content_id锛岃烦杩囬噸澶嶅唴瀹?
- **鍗曟杩愯鍐呭幓閲?*锛氬悓涓€ content 琚涓叧閿瘝鎼滅储鍒版椂锛屽彧澶勭悊涓€娆?
- **鏁版嵁搴撳眰鍘婚噸**锛歋upabase upsert + `UNIQUE(platform, content_id)` 绾︽潫淇濆簳

### 4. 缁熶竴鏁版嵁搴撶粨鏋?

鎵€鏈夊钩鍙版暟鎹啓鍏ュ悓涓€濂楄〃锛屼究浜庡悗绔法骞冲彴鏌ヨ鍒嗘瀽锛?

```text
contents          鈥?鍐呭涓昏〃 (platform + content_id 鍞竴)
comments          鈥?璇勮琛?  (platform + comment_id 鍞竴锛屽惈浜岀骇鍥炲)
creators          鈥?鍒涗綔鑰呰〃 (platform + user_id 鍞竴)
bilibili_contacts 鈥?B绔欑矇涓濆叧绯?
bilibili_dynamics 鈥?B绔欏姩鎬?
```

骞冲彴涓撴湁瀛楁瀛樺叆 `platform_data JSONB` 鍒楋紝涓嶅奖鍝嶄富琛ㄧ粨鏋勩€?

---


## 褰撳墠鐖彇鍙傛暟

| 鍙傛暟 | 鍊?| 璇存槑 |
| ---- | -- | ---- |
| `CRAWLER_MAX_NOTES_COUNT` | 30 | 姣忓叧閿瘝鏈€澶氳幏鍙?30 鏉℃悳绱㈢粨鏋?|
| `CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES` | 20 | 姣忔潯鍐呭鏈€澶氱埇 20 鏉′竴绾ц瘎璁?|
| `ENABLE_GET_SUB_COMMENTS` | True | 寮€鍚簩绾ц瘎璁猴紙鍥炲閾撅級 |
| `CRAWLER_MAX_SLEEP_SEC` | 5 | 璇锋眰闂撮殧鏈€澶?5 绉掞紙闃插皝鍙凤級 |
| `MAX_CONCURRENCY_NUM` | 1 | 鍗曠嚎绋嬮『搴忕埇鍙?|

---


## 蹇€熷紑濮?

### 鐜瑕佹眰

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)锛堝寘绠＄悊锛?
- 鏈満宸插畨瑁?Google Chrome

### 瀹夎渚濊禆

```bash
uv sync
```

### 閰嶇疆 Supabase

鍦ㄩ」鐩牴鐩綍鍒涘缓 `.env`锛堝弬鑰?`.env.example`锛夛細

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

棣栨浣跨敤闇€鍦?Supabase SQL Editor 鎵ц [schema/supabase_migration.sql](schema/supabase_migration.sql) 寤鸿〃銆?

### 杩愯

```bash
# 姝ｅ父妯″紡锛氭鏌ョ櫥褰?鈫?涓茶鐖彇鎵€鏈夐厤缃殑骞冲彴
./run_crawl.sh

# 浠呯櫥褰曪紙棣栨浣跨敤鎴?Cookie 澶辨晥鏃讹級
./run_crawl.sh --login-only

# 璺宠繃鐧诲綍妫€鏌ョ洿鎺ョ埇鍙?
./run_crawl.sh --crawl-only

# 鍗曞钩鍙扮埇鍙栵紙鐩存帴璋冪敤搴曞眰鍏ュ彛锛?
uv run main.py --platform xhs --lt qrcode --type search \
  --keywords "涓叧鏉戝闄? --save_data_option supabase
```

### 鐧诲綍鏂瑰紡

- **鎵爜鐧诲綍**锛堥粯璁わ級锛氶娆¤繍琛屾祻瑙堝櫒浼氬脊鍑轰簩缁寸爜锛屾壂鐮佸悗鐧诲綍鐘舵€佽嚜鍔ㄤ繚瀛?
- **Cookie 鐧诲綍**锛氬湪 `cookies_config.py` 涓～鍏ュ悇骞冲彴 Cookie锛屽弬鑰?`COOKIE_GUIDE.md`

---


## 椤圭洰缁撴瀯

```text
MediaCrawler/
鈹溾攢鈹€ run_crawl.sh                       # 缁熶竴杩愯鍏ュ彛锛堥厤缃叧閿瘝/骞冲彴锛?
鈹溾攢鈹€ main.py                      # 搴曞眰鐖彇鍏ュ彛锛堝崟骞冲彴锛?
鈹溾攢鈹€ config/
鈹?  鈹溾攢鈹€ base_config.py           # 鍏ㄥ眬閰嶇疆锛堢埇鍙栧弬鏁般€佽繃婊よ鍒欑瓑锛?
鈹?  鈹斺攢鈹€ {platform}_config.py    # 鍚勫钩鍙颁笓灞為厤缃?
鈹溾攢鈹€ media_platform/
鈹?  鈹斺攢鈹€ {xhs,dy,bili,wb,...}/   # 鍚勫钩鍙扮埇鍙栭€昏緫
鈹?      鈹溾攢鈹€ core.py              # 涓荤埇鍙栨祦绋?
鈹?      鈹斺攢鈹€ client.py            # API 瀹㈡埛绔?
鈹溾攢鈹€ store/
鈹?  鈹溾攢鈹€ {platform}/__init__.py  # 鍚勫钩鍙?StoreFactory
鈹?  鈹斺攢鈹€ supabase_store_impl.py  # 鍚勫钩鍙板瓧娈垫槧灏勫疄鐜?
鈹溾攢鈹€ database/
鈹?  鈹溾攢鈹€ supabase_client.py       # Supabase 鍗曚緥瀹㈡埛绔?
鈹?  鈹斺攢鈹€ supabase_store_base.py  # 缁熶竴瀛樺偍鍩虹被锛堝幓閲?+ 杩囨护閫昏緫锛?
鈹溾攢鈹€ tools/
鈹?  鈹溾攢鈹€ cdp_browser.py           # CDP 娴忚鍣ㄧ鐞嗗櫒
鈹?  鈹斺攢鈹€ browser_launcher.py      # Chrome 杩涚▼鍚姩鍣?
鈹溾攢鈹€ schema/
鈹?  鈹斺攢鈹€ supabase_migration.sql   # Supabase 寤鸿〃 SQL
鈹斺攢鈹€ browser_data/                # 娴忚鍣ㄧ櫥褰曠姸鎬佺紦瀛橈紙鏈湴锛?
```

---


## 鏁版嵁娴?

```text
run_crawl.sh
  鈹斺攢 main.py (per platform)
       鈹斺攢 core.py
            鈹溾攢 launch_browser_with_cdp()   # 鍚姩鐪熷疄 Chrome
            鈹溾攢 search_posts(keyword)        # 鍏抽敭璇嶆悳绱?
            鈹溾攢 store.store_content()        # 鐩稿叧鎬ц繃婊?鈫?Supabase upsert
            鈹溾攢 fetch_comments(content_id)   # 鐖彇璇勮
            鈹斺攢 store.store_comment()        # 鍘婚噸 鈫?Supabase upsert
```

---


## 娉ㄦ剰浜嬮」

- 鏈」鐩粎渚涘涔犲拰鍐呴儴鐮旂┒浣跨敤锛岃閬靛畧鐩爣骞冲彴鐨勬湇鍔℃潯娆?
- 寤鸿鎺у埗鐖彇棰戠巼锛岄伩鍏嶈处鍙烽闄?
- Cookie 鏈夋晥鏈熷洜骞冲彴鑰屽紓锛屽畾鏈熸鏌ョ櫥褰曠姸鎬?






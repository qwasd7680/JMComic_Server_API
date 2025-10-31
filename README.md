# RESTful API For JMComic-Crawler-Python

[![Docker Image CI](https://github.com/qwasd7680/JMComic_Server_API/actions/workflows/docker-image.yml/badge.svg)](https://github.com/qwasd7680/JMComic_Server_API/actions/workflows/docker-image.yml)
[![Pytest](https://github.com/qwasd7680/JMComic_Server_API/actions/workflows/python-app.yml/badge.svg)](https://github.com/qwasd7680/JMComic_Server_API/actions/workflows/python-app.yml)

## 项目介绍

本项目使用**Python FastAPI**软件包开发，将`JMComic-Crawler-Python`
项目提供的接口封装，便于其他开发者开发C/S的应用程序

本项目已采用**非阻塞式异步架构**，将耗时的下载任务转移到后台线程执行，并通过 WebSocket 实时向客户端推送进度通知。

### 目前已经实现的功能：
- 排行榜（每日，每周，每月，总榜）的查看
- 本子的查询（通过tag或者aid）
- 本子的标签获取
- 下载封面返回
- 下载后30分钟自动删除，节省服务器空间
- 非阻塞式下载任务启动：通过 POST 请求启动，服务器立即返回 202 Accepted。
- 通过 WebSocket 实时通知：下载和压缩状态将通过 WebSocket 连接推送给特定客户端。

### 未来打算实现的功能：
- 登陆查看收藏
- （还没想好）

## 安装教程

### 方案一. 本地部署（适用于有服务器的人）

* 获取本项目源代码
 ```shell
git clone https://github.com/qwasd7680/JMComic_Server_API
```
* 安装所需依赖
```shell
pip install -r requirements.txt
```
* 启动项目（这里的11111仅做示范，请根据实际情况调整）
```shell
gunicorn -k uvicorn.workers.UvicornWorke main:app --workers 4 --bind 0.0.0.0:11111
```

### 方案二. 使用HuggingFace Space

* 注册一个HuggingFace账号
* 打开Space页面，新建一个Space，选择Docker -> blank
* 新建一个Dockerfile
* 输入以下内容:
```dockerfile
FROM ghcr.io/qwasd7680/jmcomic_server_api:latest

COPY . /app

WORKDIR /app

RUN mkdir -p /app/temp

RUN chmod 777 /app/temp

RUN pip install -r requirements.txt

EXPOSE 7860

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorke", "main:app", "--workers", "4", "--bind", "0.0.0.0:7860"]
```

* 提交后等待build完成
* 点击"Embed this Space"
* 复制"Direct URL"，这个URL即为API地址

## 快速上手

### 1. 检查连接情况

/v1/后面直接跟时间戳即可

示例:`http://192.168.31.42:11111/v1/114514`

返回结果:
```json
{"status":"ok","app":"jmcomic_server_api","latency":"644","version": "1.0"}
```

### 2. 查看排行榜

/v1/rank/{time}

time有以下几种选择：

- month
- week
- day

其他输入则视为all（总榜）

返回结果：
```json
[{"aid":"1208626","title":"[禁漫汉化组](C106)[悠々亭(水上凛香)]オジさんの理想のカノジョ4(オリジナル)[中国翻译]"},{"aid":"1208625","title":"[禁漫汉化组](C106)[れもんのお店(古川れもん)]黒曜石の老婆のあま～いお酒(原神)[中国翻译]"},{"aid":"1208712","title":"凡人修仙传 元瑶 韩兄哪是不懂怜香惜玉？剧情 [AI Generated]"},{"aid":"1208624","title":"[超勇汉化组x禁漫天堂]WEEKLY快乐天 2025 No.29"},{"aid":"1208690","title":"[Aurora_S2] 冥河圣女と空の律者の败北物语 1-2 [AI Generated]"},{"aid":"1208643","title":"(C106)[青豆腐 (ねろましん)] なんでアタシはこんなヤツに胜てないんだ…! [中国翻译] [DL版]"},{"aid":"1208701","title":"[pii8贴图] [いーむす・アキ] ヌレスジ [DL版] [中国翻译] [pii8贴图]"},{"aid":"1208691","title":"[Aurora_S2] 『堕仙传3』璃月仙人完全降伏编 [AI Generated]"},{"aid":"1208664","title":"[Aurora_S2] 『堕仙传1』被上古邪功铭刻上淫纹的申鹤 [AI Generated]"},{"aid":"1208642","title":"在公寓偷情的人妻 -37岁的美穗- [fengfeng745个人机翻汉化] [石狩庵] 人妻、浮气、团地にて。─37岁美穂─ [中国翻译] [DL版]"},{"aid":"1208447","title":"[Mestoooo] 守岸人 [AI Generated]"},{"aid":"1208688","title":"学长，把你吃掉也可以吧？[どうしょく (あびすぐる)] 先辈、食べてもいいですか? [中国翻译] [无修正] [DL版]"},{"aid":"1208692","title":"[Aurora_S2] 『堕仙传2』堕ちた仙姉妹 [AI Generated]"},{"aid":"1208695","title":"黑色口罩玛丽概念 [白杨汉化组] (C106)[アカガイ (マインスロア)] 黒マスクマリー概念 (ブルーアーカイブ) [中国翻译] [DL版]"},{"aid":"1208702","title":"[on]指挥官よりも素敌なオスに出会ってしまった镇海[Chinese][个人机翻润色][AI Generated]"},{"aid":"1208634","title":"(PF42) [骄傲香蕉] 开走死小鬼的大车 (モンスターハンターワイルズ) [中国语] [无修正]"},{"aid":"1208694","title":"曾是最强勇者，却被夺走了恋人 ～纯洁可爱的女友被改造成淫乱模样～ [どろっぷす! (大人のSEXY绘本)] 元・最强勇者ですが恋人を寝取られました ~清楚で可憐なカノジョが淫乱改造されるまで~ [中国翻译]"},{"aid":"1208637","title":"[肾斗士汉化][Naruho-dou (Naruhodo)] シズネの淫接待"},{"aid":"1208699","title":"Fanbox漫画：产卵种族的社会性处置 (XueHuKING个人AI汉化自嵌) [白鱼京]漫画：产卵种族の社会処理"},{"aid":"1208674","title":"疯狂的妈妈游戏[K记翻译] [ジンガイラボ (めび太)] むっちり母性怪人 -狂气のお母さんごっこ- [中国翻译]"},{"aid":"1208698","title":"在今晚让我们来治愈你亲爱的~  [后勤部汉化] [ActualE Ekusu] The Night is Ours [中国翻译]"},{"aid":"1208665","title":"[Z Knight] 创世母神的即堕败北"},{"aid":"1208628","title":"[街道岚] 狙われた女骑士 催〇おじさんの復讐孕ませ生活 [AI Generated]（机翻）"},{"aid":"1208633","title":"(FF45) [骄傲香蕉] 开走死小鬼的大车2 (モンスターハンターワイルズ) [中国语] [无修正]"},{"aid":"1208650","title":"[ディビ]ご褒美はおしりに[中国翻译]"},{"aid":"1208710","title":"发情期就在今日。(骗你的) [白杨汉化组](C106)[だいおん (だいおん)] 「发情期」って嘘ついた今日。 (ブルーアーカイブ) [中国翻译] [DL版]"},{"aid":"1208629","title":"[AI翻译](C106)[あんみつよもぎ亭 (みちきんぐ)] サキュバス性徒会シコシコ执行部3 [中国翻译] [DL版]"},{"aid":"1208697","title":"淫魔邻居"},{"aid":"1208686","title":"星光下熠熠生辉的夜之记忆  [欶澜汉化组](C106)[ぽんたろ家 (ぽんたろ)] 星に染められた夜の记忆 (ブルーアーカイブ) [中国翻译] [DL版]"},{"aid":"1208696","title":"会长莉音的请求[白杨汉化组] (C106)[ZEN] 会长リオのお愿い (ブルーアーカイブ) [中国翻译] [DL版]"},{"aid":"1208675","title":"[on]铃谷と黒人スター俳优の寝取らせプレイのはずが・・・[Chinese][个人机翻润色][AI Generated]"},{"aid":"1208661","title":"[KillerT] 堕落 59"},{"aid":"1208651","title":"[ゆの汤]粗チン女将军完全マゾ豚调教 〜巨根が正义の国で短小包茎に生まれちゃったプライドの高い女将军を彻底的にわからせて杂鱼チンに相应しいマゾ豚家畜に堕とすまで〜[中国翻译] [DL版]"},{"aid":"1208667","title":"[RebornMe] 这样的理发店怎么想都不对劲 (Arknights) [AI Generated]"},{"aid":"1208648","title":"[圣华快乐书店 (如月蓝)] プリンセス・ヒプノシス ―绝伦领主の催眠で伪りの爱に堕ちる姫骑士物语 [中国翻译] [DL版]"},{"aid":"1208668","title":"[B_Meow个人汉化] (ソウル・シンクロWEST) [og、PK2 (おがた、小仓)] 黒の剑士耻辱计画 (ソードアート・オンライン)"},{"aid":"1208635","title":"TS朗君的性生活8 [きのこのみ (konomi)] TSあきら君の性生活 8 [中国翻译] [无修正] [DL版]"},{"aid":"1208672","title":"[マッド・ヴィーナス (たぶち)] 牛×兎怪人の种马係〜恶の组织に捕まったショタヒーローの贵方はどすけべ女怪人に搾られる〜 [中国翻译]"},{"aid":"1208647","title":"[Nexstat]Bar Hopping"},{"aid":"1208656","title":"[WaterBrother]Honkai:Star Rail-RuanmeiXHerta 崩坏-：星穹铁道-阮梅X黑塔 [Ai Generated]"},{"aid":"1208632","title":"春光秋逝 - 春丽别传 2[Lemonade柠檬汽水]Spring no more - Chun-Li Sidestory 2[Chinese]"},{"aid":"1208663","title":"和长着屁股毛的公司前辈一起去海边玩(C106)[没落贵族 (うぃんたぁ)] ケツ毛生えてる会社の先辈と海に行く话 [中国翻译] [DL版]"},{"aid":"1208631","title":"—关于如何合理地释放性欲—仔细调查乳头为何变硬与饥渴难耐的小穴 [小桃汉化组](C106)[カムリズム (鬼头サケル)] 合理的な性の发散についてあらためちくびカリカリイライラまんこ(ブルーアーカイブ) [中国翻译] [DL版]"},{"aid":"1208641","title":"[Finch] Cyno w/ Scara & Sethos (Japanese, Chinese)"},{"aid":"1208652","title":"和摩根陛下的新婚生活[月美汉化组] (C106)[ナツザメ] モルガン陛下と新婚生活 (Fate/Grand Order) [中国翻译] [DL版]"},{"aid":"1208660","title":"[Acbin's (あくびんす)] カウントオンミー [中国翻译] [DL版]"},{"aid":"1208689","title":"(cqxl自己汉化)[ちょっとB専] お兄ちゃんの家庭教师に一目惚れ！(cqxl自己汉化)（Chinese）"},{"aid":"1208685","title":"(C105) [ぽてとさらだ (ヒめくり)] 住めばミヤコ! Vol.3 [中国翻译]"},{"aid":"1208676","title":"[on]ローンは嫌々ながら寝取らせプレイに付き合ってくれる4[Chinese][个人机翻润色][AI Generated]"},{"aid":"1208684","title":"[Yubi] もしもハンコックがオペオペの实の前任者にエッチなことされたら... (ワンピース) [中国翻译]"},{"aid":"1208659","title":"后辈的乳首责2 [MTL] [プライドビーンズ] 后辈ちゃんのいじわる乳首责め2 [中国翻译] [DL版]"},{"aid":"1208546","title":"誓约[欶澜汉化组](C106)[Horizontal World (またのんき)] 誓ア约 (ブルーアーカイブ) [中国翻译] [DL版]"},{"aid":"1208681","title":"(C106)[ELHEART'S (息吹ポン)] ある日突然○○になった某エリート (机动战士Gundam GQuuuuuuX)"},{"aid":"1208644","title":"[busydege] 奥特战姬露娜（8章合集）"},{"aid":"1208666","title":"（个人汉化）[8ヲラ]作中最强キャラが续编で嚙ませになるやつ"},{"aid":"1208640","title":"雌牛母女 [Bismuth个人汉化] [熊三] ウシ亲子 [中国翻译] [Bismuth个人汉化]"},{"aid":"1208671","title":"[くぎどうふ (かすがい)] 消えないメメント (东方Project) [中国翻译] [DL版]"},{"aid":"1208670","title":"独翼天使的 无解恒弁题  [下江小春汉化组](C106)[ヨリドリミドリ (赫白きいろ)] 片翼のアンチノミー (ブルーアーカイブ) [中国翻译] [DL版]"},{"aid":"1208679","title":"EP5 女儿幼妻长门酱的早晨运动 [AI Generated]"},{"aid":"1208646","title":"[黒杜屋 (黒田クロ)] むちむち肉感Mカップふたなり母娘のびちょ濡れ汗だく家庭内SEX [中国翻译] [DL版]"},{"aid":"1208669","title":"[たた] 今年の一月に出したかったやつ (ブリーチ) [中国翻译]"},{"aid":"1208673","title":"木乃伊战士-生日快乐（K记翻译） [RuinCounty] Mummies Alive!_ Happy Birthday"},{"aid":"1208693","title":"[electric sheep] 女头首 家畜奴隷堕ち 〜报復の肉体改造地狱〜（中国语）（yzdtom个人汉化）"},{"aid":"1208677","title":"[さいだ一明]水に栖む淫念"},{"aid":"1208639","title":"再来点！小乖乖[涩涩人个人机翻润色](C106)[こむぎばたけ (こむぎ)] もっと！おりこうさん [中国翻译] [DL版]"},{"aid":"1208680","title":"[しもやけ堂 (逢魔刻壹)] マミゾウのおつまみ (东方Project) [中国翻译] [DL版]"},{"aid":"1208682","title":"(フリートドック神户) [雨月の雫 (月出里)] ひとり游びなんてシてないもん! (舰队これくしょん -舰これ-) [中国翻译]"},{"aid":"1208662","title":"[AI小松鸟]战术学院等候的爱夜❤️与胡腾老婆共处的私密恋爱教室❤️ [AI Generated]"},{"aid":"1208687","title":"joseph - 筹集旅费 [AI Generated]"},{"aid":"1208654","title":"和露西在家约会的按摩服务[白杨汉化组] (C106)[あとりえひなた (ひなた悠)] ルーシーとおうちデートでマッサージ (ゼンレスゾーンゼロ) [中国翻译] [DL版]"},{"aid":"1208615","title":"别再搞发明了！冒失鬼店长大人！"},{"aid":"1208655","title":"[个人机翻润色] [The Nation of Head Scissors (トッポギ)] Girls Beat! -vsマリ- [中国翻译]"},{"aid":"1208658","title":"[白杨汉化组](C106)[ろきそにん工房 (ろきた)] 门主之蜜情 贰 (ブルーアーカイブ) [中国翻译] [DL版]"},{"aid":"1208683","title":"[ぽてとさらだ (ヒめくり)] ポプニ系女子パニック！Vol. 10 [中国翻译] [DL版]"},{"aid":"1208653","title":"Cute Loli's,Femboys and more... [AI Generated]"},{"aid":"1208678","title":"警察的食谱[马栏山汉化组][NANASHI (ニル)] 巡查へのレシピ [中国翻译] [DL版]"},{"aid":"1208638","title":"老师我来给您按摩吧[欶澜汉化组] (C106)[ぐりいん野はうす (温野りょく)] 先生、マッサージしてあげよっか? (ブルーアーカイブ) [中国翻译] [DL版]"},{"aid":"1208729","title":"[不咕鸟汉化组] [黄金绅士俱乐部 (41)] 母さんはホームヘルパー〜部屋の片付けから性欲処理まで [中国翻译]"},{"aid":"1208733","title":"[KawaGawa] 用快感存储驯服杀手吧！(Arknights) [Chinese] [AI Generated]"},{"aid":"1208645","title":"萝莉与姐姐 [Bismuth个人汉化] [熊三] ロリおね"}]
```
返回结构:
```json
[{"aid":"114514","title":"陵长镜简直是个尤物啊"}]
```

### 3. 搜索本子

只有排行榜肯定不够，我们还需要能够搜索本子的功能

/v1/search/{tag}/{num}

tag指的搜索关键词，可以是标签，作者，标题等等，num则代表页数

示例:`http://192.168.31.42:11111/v1/search/原神/1`

返回结果:
```json
[{"album_id":"1208664","title":"[Aurora_S2] 『堕仙传1』被上古邪功铭刻上淫纹的申鹤 [AI Generated]"},{"album_id":"1208641","title":"[Finch] Cyno w/ Scara & Sethos (Japanese, Chinese)"},{"album_id":"1208625","title":"[禁漫汉化组](C106)[れもんのお店(古川れもん)]黒曜石の老婆のあま～いお酒(原神)[中国翻译]"},{"album_id":"1208409","title":"[Finch] Bennett x Xbalanque (Genshin Impact) [Chinese]"},{"album_id":"1208403","title":"纳西妲掰开小穴给你看"},{"album_id":"1208393","title":"[Aurora_S2] 堕仙传02 堕ちた仙姉妹 [AI Generated]"},{"album_id":"1208257","title":"卡齐娜酱还好吗？ [欶澜汉化组] (C106) [キャビラムール (ジラ壹)] カチーナちゃん大丈夫? (原神) [中国翻译]"},{"album_id":"1207994","title":"[2AM (2)] Pierce (Genshin Impact) 原神阿乔x基尼奇"},{"album_id":"1207951","title":"Catberryw | Zhongli × Yelan — Night Audit of Legends"},{"album_id":"1207923","title":"稻妻烟雾缭绕钱汤夜话 [禁漫汉化组] (C106) [丸杏亭(マルコ)] 稻妻汤けむり钱汤夜话 (原神) [中国翻译]"},{"album_id":"1207922","title":"旅行者ｘ茜特拉莉 作品短篇集 [禁漫汉化组] (C106) [Goomin(ぐみみ)] 旅人×シトラリ作品短编集 (原神) [中国翻译]"},{"album_id":"1207801","title":"公爵与MOB暴徒 [Cal汉化] [nogcha] 공작님 모브물-2 [Chinese] [full color]"},{"album_id":"1207407","title":"原神"},{"album_id":"1207400","title":"[Ururu] 原神-变数 END [中国语]"},{"album_id":"1206579","title":"[トリニティ水着接待部] フィッシュルアビス堕ち (原神)"},{"album_id":"1206578","title":"[トリニティ水着接待部] モンド城陷落～メスブタ改造工场～ (原神)"},{"album_id":"1206237","title":"【kocchi】Fantasmagoria(原神赛诺x提纳里)"},{"album_id":"1206201","title":"[雪ノ岚&异端丶] 愿绳绮梦谭（全）"},{"album_id":"1205997","title":"[四字真言] 芙宁娜[AI Generated]"},{"album_id":"1205959","title":"[saya_触手酱] 【仆人】阿蕾奇诺（中文"},{"album_id":"1205958","title":"[saya_触手酱] 若娜瓦（中文"},{"album_id":"1205954","title":"【Qshika】KazuhaXAether(原神枫原万叶x空)"},{"album_id":"1205943","title":"[Magic_Xiang] 荧&甘雨 (Genshin Impact) [Chinese]"},{"album_id":"1205573","title":"【kocchi】Fantasmagoria(原神赛诺x提纳里)【chinese】"},{"album_id":"1205246","title":"[Andy763] 愚影下的亡灵 附身芭芭拉"},{"album_id":"1204360","title":"纳西妲的拷问二"},{"album_id":"1203940","title":"[黎欧出资汉化][腹イタ产业 (シロパカ)] 稻妻ノ性教育 (原神) [中国翻译] [DL版]"},{"album_id":"1203778","title":"[Arlanmi] 2025-06-30 Eula-152p [AI Generated]"},{"album_id":"1203773","title":"[Arlanmi] 2025-07-28 Navia-155p [AI Generated]"},{"album_id":"1203763","title":"女仆游戏 [男男菊花香汉化] (星に愿いを2025) [5つ星レストラン (しろまる)] メイドユウギ (原神) [中国翻译]"},{"album_id":"1203726","title":"[Qshika] 托马X小鹿"},{"album_id":"1203535","title":"【バッキンガム(森モリィ）《 Cake Bite》莱欧斯利x那维莱特 狱审 (原神)"},{"album_id":"1203518","title":"[RetroCyber 个人汉化] [Vel] 原神TSF：冒牌货"},{"album_id":"1203265","title":"女仆游戏(原神)(星に愿いを2025)【男男菊花香汉化】 [5つ星レストラン (しろまる)] メイドユウギ (原神)"},{"album_id":"1202772","title":"[386歪汉化] [Paya8] ヴァレサマンガ (原神) [中国翻译]"},{"album_id":"1202538","title":"原神-申鹤与路过黑人的故事[AI Generated]"},{"album_id":"1202116","title":"[Horori] Teyvat Gravure #09 (原神) [中国翻译] [无修正]"},{"album_id":"1202427","title":"恶龙刨削 (E long pao xue) cosplay Furina – Genshin Impact"},{"album_id":"1202419","title":"[AhandsomeA]丝柯克Skirk"},{"album_id":"1202314","title":"[Rogan个人翻译][Horori] Teyvat Gravure #10 (原神)"},{"album_id":"1202123","title":"PoppaChan cosplay Greater Lord Rukkhadevata – Genshin Impact"},{"album_id":"1202124","title":"李佳 cosplay Raiden Shogun – Genshin Impact"},{"album_id":"1202211","title":"[可以瑟瑟] 重生之散兵竟是我自己（无修版）"},{"album_id":"1201619","title":"[RetroCyber & 未命名ver.α 合作汉化] [Vel] 进入深渊 (Genshin Impact)"},{"album_id":"1201265","title":"【 绫华 & 空 】 一直在一起好吗？"},{"album_id":"1201124","title":"[Shaggy SUSU] スカーク (原神) [日本语、中国语]"},{"album_id":"1200760","title":"[无名老图] ロノヴァＶＳ种付けおじさん"},{"album_id":"1200759","title":"[无名老图] フォンテーヌドスケベ映影ランド"},{"album_id":"1200758","title":"[无名老图] アビスのメスブタ雷电将军败北公开凌辱"},{"album_id":"1200756","title":"[无名老图] スカークさんはおじさん専用肉オナホ"},{"album_id":"1200755","title":"[无名老图]  催眠游郭の国スメール"},{"album_id":"1200754","title":"[无名老图] チ●ポに败北宣言しちゃうスカークさん"},{"album_id":"1200539","title":"[焚心绚华绘赞助] [毒猫ノイル] 胡桃に恶いことをする话 【后编】[无修正]"},{"album_id":"1200540","title":"[焚心绚华绘赞助] [毒猫ノイル] 胡桃に恶いことをする话【前编】 (原神) [无修正]"},{"album_id":"1200265","title":"[菜さん]原神剧情顺序全集整理"},{"album_id":"1200238","title":"[Gorani] Raiden's Horse Mating Show (原神) [中国翻译] [机翻]"},{"album_id":"1200055","title":"Bangni邦尼 cosplay Yae Miko – Genshin Impact"},{"album_id":"1200165","title":"【小柴胡】茜特菈莉放置"},{"album_id":"1199896","title":"[Hotaru] Futanari Hotaru no Bouken 111 Xilonen"},{"album_id":"1199487","title":"慕慕Momo cosplay Mirror Maiden – Genshin Impact"},{"album_id":"1199485","title":"阿薰kaOri (axunkaOri) cosplay Mavuika – Genshin Impact"},{"album_id":"1199141","title":"Okita Rinka (沖田凛花Rinka) cosplay Yelan – Genshin Impact"},{"album_id":"1198962","title":"[颠佬旅者汉化组] [Poyeop] 胡桃 2 "},{"album_id":"1198581","title":"[柯莱个人翻译][ROD.WEL]Raiden (GenshinImpact)"},{"album_id":"1198106","title":"【Milk猫】空X提米：不好意思把你弄「溼」了"},{"album_id":"1198067","title":"[オルガムスラップ (いちのみるく)] 地脉异常で动物化&发情して本能のままスケベしまくる话 [中国翻译] [DL版]"},{"album_id":"1197207","title":"Asagi Kawaii cosplay Mualani – Genshin Impact"},{"album_id":"1197209","title":"ZinieQ cosplay Xilonen – Genshin Impact"},{"album_id":"1196932","title":"[megumignsn] Love of Haravatat requires no words｜知论派的爱意无需言语"},{"album_id":"1196776","title":"第一章 - 神里家的复兴（1"},{"album_id":"1196584","title":"[Kerberus] 福利姬6"},{"album_id":"1196583","title":"[Kerberus] 福利姬5"},{"album_id":"1196428","title":"Kyokoyaki cosplay Ayaka Kamisato – Genshin Impact"},{"album_id":"1196409","title":"[RoyBoy] 与丝丝酱的同居日常 (原神)"},{"album_id":"1195896","title":"[remora] シトラリとイチャイチャ (原神) [中国翻译]"},{"album_id":"1195748","title":"[シロパカ] 流泉の众には笔おろしの文化があるらしい (原神) [中国翻译]"},{"album_id":"1195747","title":"[シロパカ] シトラリがお持ち归りされて、ナウいセックスを体验する话(´・∀・｀) (原神) [中国翻译]"},{"album_id":"1195344","title":"[PShiro]夜阑"},{"album_id":"1195341","title":"[Fuzume] Klee Muchi Situ (Genshin Impact)-1280x。"},{"album_id":"1195299","title":"【pcrow】Childe x Aether Lost kingdom seggs｜公子x空 失落王国的情欲"}]
```

返回结构与上面一致

### 4. 本子详情

/v1/info/{aid}

显而易见，传入aid即可

###### 需要注意的是，由于api不会返回本子的页数，我们会优先使用html方式，但是jmcomic有地区限制，导致日本ip无法访问，因此我们将会在启动时自动检测能否使用html方式，如果不能，将会自动切换为api方式

返回示例:
```json
{"status":"success","tag":["全彩","巨乳","强姦","强暴","CG集","AI绘图","中文"],"view_count":"102497","like_count":"42","page_count":"20","method": "html"}
```

### 5. 本子封面

/v1/get/cover/{aid}

传入aid，可以直接返回该album的cover.jpg，适合直接放入如SwiftUI的AsyncImage组件中使用

示例:`http://192.168.31.42:11111/v1/get/cover/42256`

返回示例:![00001.webp](./0001.png)

手动打码（陵长镜：~~没有我十分之一可爱~~）

### 6. 下载本子(异步任务 + WebSocket 实时通知)

**此环节已升级为异步任务和 WebSocket 实时通知机制，以避免阻塞服务器。 客户端需要两个步骤来完成下载：**

#### 6.1 建立 WebSocket 连接 (监听通知)

首先，客户端需要建立一个持久的 WebSocket 连接来接收下载状态通知。

**Endpoint: `/ws/notifications/{client_id}`**
**Method: `WS` (WebSocket)**
参数:

- client_id: 客户端的唯一标识符（例如 UUID），用于服务器精准推送通知。

示例: `ws://192.168.31.42:11111/ws/notifications/unique-client-uuid`

#### 6.2 启动下载任务 (非阻塞式 POST)

客户端发起下载任务请求。服务器会立即将任务放入后台线程池并返回 202 Accepted，不会阻塞。

**Endpoint: `/v1/download/album/{album_id}`**
**Method: `POST`**
参数:

- album_id: 本子号。

**请求体 (Body - JSON):** 必须包含步骤 6.1 中使用的 `client_id`。
```
{
    "client_id": "unique-client-uuid"
}
```
**成功启动返回示例 (HTTP 202):**

`{"status": "processing", "message": "下载任务已在后台启动，请通过 WebSocket 监听 'download_ready' 通知。"}`

#### 6.3 接收通知并下载文件

**当后台任务完成下载和压缩后，服务器将通过 WebSocket 向对应的 `client_id` 推送通知：**

**WebSocket 通知示例:**
```
{
    "status": "download_ready",
    "file_name": "【KawaGawa】姐姐大赛（上）",
    "message": "文件 '【KawaGawa】姐姐大赛（上）' 已完成处理，可以下载。"
}
```
客户端收到此通知后，即可使用 `/v1/download/{file_name}` 接口下载文件：

**下载 Endpoint: `/v1/download/{file_name}`**
**Method: `GET`**

只需要传入通知中返回的 `file_name`，即可将打包的 zip 文件返回，文件名格式为 `"{file_name}.zip"`。

## 感谢以下项目

### 禁漫Python爬虫

<a href="https://github.com/hect0x7/JMComic-Crawler-Python">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=hect0x7&repo=JMComic-Crawler-Python&theme=radical" />
    <source media="(prefers-color-scheme: light)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=hect0x7&repo=JMComic-Crawler-Python" />
    <img alt="Repo Card" src="https://github-readme-stats.vercel.app/api/pin/?username=hect0x7&repo=JMComic-Crawler-Python" />
  </picture>
</a>
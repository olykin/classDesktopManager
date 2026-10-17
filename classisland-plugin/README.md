# classDesktopManager 课程联动

这个插件把 [ClassIsland](https://github.com/ClassIsland/ClassIsland) 的**当前课程**同步给 [classDesktopManager](https://github.com/olykin/classDesktopManager)：老师在上「数学」课时，新出现在桌面或下载文件夹里的文件就会优先建议归档到「数学」文件夹。

## 它做了什么

- 订阅 ClassIsland 的上课、课间、放学和状态变化事件；
- 把这些信息写入 `%APPDATA%\classDesktopManager\classisland.json`（每 10 秒还会心跳更新一次）；
- classDesktopManager 读取这个文件后，会把「当前课程」作为文件归档的优先建议，也可以设置为上课时自动归档。

## 安装

- 在 ClassIsland 的插件商店里搜索「classDesktopManager 课程联动」安装；或
- 从 [Release](https://github.com/olykin/classDesktopManager/releases/tag/1.0.0.0) 下载
  `ClassDesktopManagerBridge.cipx`，在 ClassIsland「插件」页导入后重启。

## 在 classDesktopManager 里开启

1. 安装本插件并重启 ClassIsland；
2. 打开 classDesktopManager →【设置】→「ClassIsland 课程联动」，勾选
   「按 ClassIsland 当前课程建议归档科目（默认关闭）」；
3. 需要的话再勾选「上课时直接归档到对应科目文件夹，不再弹气泡」；
4. 卡片下方显示「当前课程：数学（OnClass）」即表示连接正常，可点「刷新状态」复查。

## 注意

- 状态文件只在本机读写，不会联网；
- ClassIsland 未运行或超过 60 秒没有更新时，classDesktopManager 会自动忽略课程信息；
- 课程名要和 classDesktopManager 设置里的科目文件夹名对得上（例如「数学」）。

## 许可证

GPL-3.0-or-later。

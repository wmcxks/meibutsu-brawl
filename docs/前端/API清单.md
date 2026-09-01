# 微信小游戏 API 清单

本项目用到的微信小游戏 API 按功能分类整理如下。

---

## 1. 画布与渲染

游戏所有内容都绘制在 Canvas 上，这是最核心的 API。

| API | 说明 | 使用场景 |
|-----|------|---------|
| `wx.createCanvas()` | 创建游戏主画布 | 游戏启动时创建，全局唯一 |
| `canvas.getContext('2d')` | 获取 2D 渲染上下文 | 绑定 ctx 后绘制所有内容 |
| `requestAnimationFrame(cb)` | 请求下一帧回调 | 驱动游戏主循环（60fps） |
| `cancelAnimationFrame(id)` | 取消帧回调 | 暂停游戏时停止循环 |

**示例：**
```js
const canvas = wx.createCanvas()
const ctx = canvas.getContext('2d')

function gameLoop() {
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  // 绘制逻辑...
  requestAnimationFrame(gameLoop)
}
requestAnimationFrame(gameLoop)
```

---

## 2. 图片资源

用于加载卡片图标、背景图等游戏素材。

| API | 说明 | 使用场景 |
|-----|------|---------|
| `wx.createImage()` | 创建 Image 对象 | 加载 png/jpg 图片资源 |
| `image.src` | 设置图片路径 | 指定要加载的图片 |
| `image.onload` | 图片加载完成回调 | Loading 场景统计加载进度 |
| `image.onerror` | 图片加载失败回调 | 错误处理 |
| `ctx.drawImage()` | 将图片绘制到画布 | 渲染卡片、背景等 |

**示例：**
```js
const img = wx.createImage()
img.src = 'images/card.png'
img.onload = () => {
  ctx.drawImage(img, x, y, width, height)
}
```

---

## 3. 触摸事件

小游戏没有鼠标，全靠触摸事件响应玩家操作。

| API | 说明 | 使用场景 |
|-----|------|---------|
| `wx.onTouchStart(cb)` | 手指触摸屏幕 | 检测玩家点击了哪张卡片 |
| `wx.onTouchMove(cb)` | 手指在屏幕上移动 | 预留拖拽功能 |
| `wx.onTouchEnd(cb)` | 手指离开屏幕 | 确认点击操作 |
| `wx.offTouchStart(cb)` | 取消触摸监听 | 场景切换时清理事件 |

**回调参数：**
```js
wx.onTouchStart((e) => {
  const touch = e.touches[0]
  const x = touch.clientX  // 触摸点 X 坐标
  const y = touch.clientY  // 触摸点 Y 坐标
})
```

---

## 4. 系统信息

获取设备信息，用于屏幕适配。

| API | 说明 | 使用场景 |
|-----|------|---------|
| `wx.getSystemInfoSync()` | 同步获取系统信息 | 启动时获取屏幕宽高 |
| `wx.getWindowInfo()` | 获取窗口信息 | 获取可用区域尺寸 |
| `wx.getDeviceInfo()` | 获取设备信息 | 判断设备类型 |

**常用字段：**
```js
const info = wx.getSystemInfoSync()
info.screenWidth   // 屏幕宽度（px）
info.screenHeight  // 屏幕高度（px）
info.pixelRatio    // 设备像素比
info.platform      // 平台：ios / android / devtools
```

---

## 5. 网络请求

与后端 API 通信，用于登录、获取关卡、提交成绩等。

| API | 说明 | 使用场景 |
|-----|------|---------|
| `wx.request()` | 发起 HTTP 请求 | 调用后端所有接口 |

**示例：**
```js
wx.request({
  url: 'https://your-server.com/api/level/config',
  method: 'GET',
  header: {
    'Authorization': `Bearer ${token}`
  },
  success(res) {
    console.log(res.data)
  },
  fail(err) {
    console.error('请求失败', err)
  }
})
```

---

## 6. 登录与用户

授权作为进入游戏的前置场景：`loading` 完成后若本地无 token 则强制跳到 `scenes/auth.js`，用户必须点击微信授权按钮才能进菜单。

| API | 说明 | 使用场景 |
|-----|------|---------|
| `wx.login()` | 获取登录 code | 授权按钮 onTap 回调内调用，code 发给后端换 token |
| `wx.createUserInfoButton()` | 创建小游戏专用的授权按钮 | auth 场景中可见，一次性拿到昵称+头像 |
| `wx.setStorageSync / getStorageSync` | 本地持久化 token + 用户信息 | 避免重复登录 |

> 小游戏环境下 `wx.getUserProfile` 已废弃，必须使用 `wx.createUserInfoButton` 触发授权。

**完整授权流程（auth 场景）：**
```js
const btn = wx.createUserInfoButton({
  type: 'text', text: '微信授权登录',
  style: { left: 80, top: 600, width: 240, height: 50,
           backgroundColor: '#07C160', color: '#ffffff',
           textAlign: 'center', fontSize: 18, borderRadius: 25 },
  withCredentials: false, lang: 'zh_CN'
})
btn.onTap((res) => {
  if (!res.userInfo) return  // 用户拒绝
  // 1) wx.login 拿 code → POST /api/auth/login 换 token
  // 2) POST /api/auth/update-profile 写回昵称头像
  // 3) token + userInfo 保存到 wx.setStorageSync，跳 menu
})
```

---

## 7. 本地存储

在设备本地保存数据，断网也能用。

| API | 说明 | 使用场景 |
|-----|------|---------|
| `wx.setStorageSync(key, value)` | 同步写入本地存储 | 保存 token、游戏设置 |
| `wx.getStorageSync(key)` | 同步读取本地存储 | 读取已保存的数据 |
| `wx.removeStorageSync(key)` | 同步删除本地存储 | 清除登录态 |

**示例：**
```js
// 保存设置
wx.setStorageSync('settings', { sound: true, music: true })

// 读取设置
const settings = wx.getStorageSync('settings')
```

---

## 8. 音频

背景音乐和消除音效。

| API | 说明 | 使用场景 |
|-----|------|---------|
| `wx.createInnerAudioContext()` | 创建音频实例 | 播放音效和背景音乐 |
| `audio.src` | 设置音频路径 | 指定音频文件 |
| `audio.play()` | 播放 | 触发消除时播放音效 |
| `audio.pause()` | 暂停 | 游戏暂停时静音 |
| `audio.loop` | 是否循环 | 背景音乐设为 true |

**示例：**
```js
// 背景音乐
const bgm = wx.createInnerAudioContext()
bgm.src = 'audio/bgm.mp3'
bgm.loop = true
bgm.play()

// 消除音效
const sfx = wx.createInnerAudioContext()
sfx.src = 'audio/match.mp3'
sfx.play()  // 每次消除时调用
```

---

## 9. 分享

支持分享到好友和群。本项目的分享用在两处：
1. **道具分享解锁**：关卡内点道具时弹 `dialogs/propShare.js` 弹窗，点"分享获取"按钮调用 `wx.shareAppMessage`，分享成功后道具数量 +1。
2. **通关分享**：`dialogs/win.js` 通关弹窗内提供分享按钮，把成绩晒给好友。

| API | 说明 | 使用场景 |
|-----|------|---------|
| `wx.shareAppMessage()` | 主动分享（需由按钮点击触发） | 道具分享、通关分享 |
| `wx.onShareAppMessage(cb)` | 监听右上角菜单分享 | 设置默认分享内容 |
| `wx.showShareMenu()` | 启用右上角分享菜单 | 游戏启动时调用一次 |

**默认分享内容（右上角菜单）：**
```js
wx.showShareMenu({ withShareTicket: false })
wx.onShareAppMessage(() => ({
  title: '名物大乱斗 - 你能打通第几关？',
  imageUrl: 'images/share.png'
}))
```

**主动分享（道具/通关弹窗内）：**
```js
wx.shareAppMessage({
  title: '名物大乱斗 - 帮我点一下就能多一个道具！',
  imageUrl: 'images/share.png'
})
// 小游戏环境下 shareAppMessage 没有 success 回调
// 采用 wx.onShow 在分享返回后判定分享行为是否完成
```

---

## 10. 界面

菜单样式、Loading 提示等。

| API | 说明 | 使用场景 |
|-----|------|---------|
| `wx.setMenuStyle()` | 设置菜单按钮样式 | 适配深色/浅色主题 |
| `wx.showToast()` | 显示提示框 | 操作反馈（如"分享成功 +1 道具"） |
| `wx.showModal()` | 显示确认弹窗 | 注：项目内主要用自绘 Canvas 弹窗（`dialogs/confirm.js`）替代，保证视觉风格统一 |
| `wx.showLoading()` | 显示加载动画 | 网络请求等待时 |

> **注意**：本项目所有游戏内弹窗（确认退出 / 复活 / 通关 / 道具分享）均为自绘 Canvas 弹窗，位于 `client/scenes/game/dialogs/` 目录，不使用系统 `showModal`，以保证 UI 风格与主界面一致。

---

## 11. 渲染相关非微信 API 约定

虽不是 `wx.*` API，但项目内高频使用，整理如下：

| API | 说明 | 典型调用处 |
|-----|------|-----------|
| `ctx.save() / ctx.restore()` | 保存/恢复画布状态 | 所有 `renders/*.js` 在改 alpha/transform 前后必须成对调用 |
| `ctx.globalAlpha` | 全局透明度 | `renders/endFx.js` 全屏结算特效渐入渐出 |
| `ctx.translate / scale / rotate` | 坐标系变换 | `renders/flyAnim.js` 卡牌飞入槽位动画 |
| `ctx.fillText()` + `textAlign/textBaseline` | 文本绘制 | `renders/timer.js` 关卡计时器、弹窗标题 |
| `Date.now()` | 高精度时间戳 | 计时器 `levelStartTime` 与动画插值 |

---

## 优先级总结

| 优先级 | API 分类 | 原因 |
|--------|---------|------|
| P0 必须 | 画布渲染、图片、触摸事件 | 没有这些游戏跑不起来 |
| P1 重要 | 系统信息、网络请求、登录 | 适配和用户体系 |
| P2 增强 | 音频、本地存储 | 提升游戏体验 |
| P3 已落地 | 分享（道具解锁/通关分享） | 已通过 `dialogs/propShare.js`、`dialogs/win.js` 接入 |

/**
 * WebAdapter.ts
 * 纯 Web 平台适配器：无需任何第三方 SDK。
 * - login(): 生成本地 UUID（guest_uuid）调用后端 /api/auth/guest-login 换取 JWT
 * - share(): 优先 Web Share API，不支持时降级为复制链接 + 控制台提示
 */

import { loginAsGuest } from '../api/request'
import type { ISDKAdapter } from './ISDKAdapter'

export class WebAdapter implements ISDKAdapter {
  readonly platform = 'web'

  async init(): Promise<void> {
    // 纯浏览器环境无需平台初始化。
  }

  async login(): Promise<string> {
    // 游客静默登录：本地 UUID -> JWT（内部已存储 Token 并返回）
    return loginAsGuest()
  }

  share(data: any): void {
    if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
      navigator.share(data as ShareData).catch((err) => {
        console.warn('[share] Web Share API 调用失败:', err)
      })
      return
    }
    console.warn('[share] 当前浏览器不支持 Web Share API:', data)
  }
}

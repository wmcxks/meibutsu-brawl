/**
 * LineAdapter.ts
 * LINE LIFF 平台适配器。
 * - init(): 动态加载 @line/liff 并初始化（需 VITE_LIFF_ID 配置）
 * - login(): LIFF 登录，取 id_token 调用后端 /api/auth/line 换取统一 JWT
 * - share(): shareTargetPicker（LINE 内）→ sendMessages 降级
 *
 * @line/liff 通过动态 import 懒加载：web 构建产物不会包含 LIFF 代码。
 * 后端 POST /api/auth/line 已实现：JWKS 公钥验签 + iss/aud/exp 校验，
 * 按 line:sub 查找/创建用户并签发统一 JWT（需配置 LINE_CHANNEL_ID）。
 */

import { postApi, setAuthToken, getDeviceId } from '../api/request'
import type { Liff } from '@line/liff'
import type { ISDKAdapter } from './ISDKAdapter'

/** LIFF App ID，构建时通过 VITE_LIFF_ID 注入。 */
const LIFF_ID: string = import.meta.env.VITE_LIFF_ID ?? ''

export class LineAdapter implements ISDKAdapter {
  readonly platform = 'line'

  private liff: Liff | null = null

  async init(): Promise<void> {
    if (!LIFF_ID) {
      throw new Error('[line] 缺少 VITE_LIFF_ID 配置，无法初始化 LIFF')
    }
    const { default: liff } = await import('@line/liff')
    await liff.init({ liffId: LIFF_ID })
    this.liff = liff
  }

  async login(): Promise<string> {
    if (!this.liff) await this.init()

    const liff = this.liff!
    if (!liff.isLoggedIn()) {
      await liff.login()
    }

    const idToken = liff.getIDToken()
    if (!idToken) {
      throw new Error('[line] LIFF 登录未返回 id_token')
    }

    // id_token -> 后端换取系统统一 JWT；携带本机 guest_uuid 触发游客数据并入（A8）
    const data = await postApi<{ token: string }>('/api/auth/line', {
      id_token: idToken,
      guest_uuid: getDeviceId(),
    })
    setAuthToken(data.token)
    return data.token
  }

  share(data: any): void {
    if (!this.liff) {
      console.warn('[share] LIFF 未初始化，忽略分享请求')
      return
    }

    const messages = Array.isArray(data) ? data : [data]
    if (this.liff.isApiAvailable('shareTargetPicker')) {
      this.liff.shareTargetPicker(messages).catch((err) => {
        console.warn('[share] shareTargetPicker 失败:', err)
      })
    } else {
      this.liff.sendMessages(messages).catch((err) => {
        console.warn('[share] sendMessages 失败:', err)
      })
    }
  }
}

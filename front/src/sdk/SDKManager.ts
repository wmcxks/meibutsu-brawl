/**
 * SDKManager.ts
 * 平台适配器工厂（单例）：依据构建期环境变量 VITE_TARGET_PLATFORM
 * 动态实例化并返回对应的平台适配器。
 *
 *   VITE_TARGET_PLATFORM=web   -> WebAdapter（默认）
 *   VITE_TARGET_PLATFORM=line  -> LineAdapter
 *
 * 扩展新平台只需三步：
 *   1. 新建 XxxAdapter.ts 实现 ISDKAdapter
 *   2. 在 createAdapter() 的 switch 中注册一行
 *   3. 构建时设置 VITE_TARGET_PLATFORM=xxx
 * 业务层零改动。
 */

import type { ISDKAdapter } from './ISDKAdapter'
import { WebAdapter } from './WebAdapter'
import { LineAdapter } from './LineAdapter'

class SDKManagerImpl {
  private static _instance: SDKManagerImpl | null = null

  private _adapter: ISDKAdapter | null = null

  private constructor() {}

  static get instance(): SDKManagerImpl {
    if (!SDKManagerImpl._instance) {
      SDKManagerImpl._instance = new SDKManagerImpl()
    }
    return SDKManagerImpl._instance
  }

  /** 当前平台适配器（懒实例化，首次访问时创建）。 */
  get adapter(): ISDKAdapter {
    if (!this._adapter) {
      this._adapter = this.createAdapter()
    }
    return this._adapter
  }

  private createAdapter(): ISDKAdapter {
    const platform: string = import.meta.env.VITE_TARGET_PLATFORM ?? 'web'

    switch (platform) {
      case 'web':
        return new WebAdapter()
      case 'line':
        return new LineAdapter()
      default:
        throw new Error(`[sdk] 未注册的平台适配器: ${platform}（VITE_TARGET_PLATFORM 仅支持 web / line）`)
    }
  }
}

/** 全局单例：使用方式 await SDKManager.adapter.init() */
export const SDKManager = SDKManagerImpl.instance

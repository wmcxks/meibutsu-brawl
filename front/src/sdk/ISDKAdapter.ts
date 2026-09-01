/**
 * ISDKAdapter.ts
 * 跨平台 SDK 标准接口：所有平台适配器（Web / LINE / 抖音 / ...）必须实现。
 *
 * 上层（main.ts / 业务代码）只依赖此接口：
 *   await SDKManager.adapter.init()   // 平台初始化（如 LIFF init）
 *   await SDKManager.adapter.login()  // 登录，返回系统统一 JWT
 *   SDKManager.adapter.share(data)    // 平台分享
 * 从而完全抹平平台差异，做到「一套代码，多端发布」。
 */
export interface ISDKAdapter {
  /** 平台标识（'web' | 'line' | ...），用于日志与调试。 */
  readonly platform: string

  /**
   * 平台初始化（如 LINE LIFF init / 其他平台 SDK 注册）。
   * 失败应抛出异常，由上层决定降级策略。
   */
  init(): Promise<void>

  /**
   * 登录并返回系统统一的 JWT（后端签发的标准 Token）。
   * 实现方负责平台侧认证（游客 UUID / LIFF id_token）到 JWT 的换取，
   * 并将 JWT 写入统一存储（localStorage），供请求层自动携带。
   */
  login(): Promise<string>

  /**
   * 平台分享能力（如 LINE shareTargetPicker / Web Share API）。
   * 各平台对 payload 结构要求不同，由各适配器自行解释。
   */
  share(data: any): void
}

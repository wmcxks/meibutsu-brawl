"""应用配置 — 从环境变量 / .env 文件读取"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """全局配置项，通过环境变量或 .env 文件注入"""

    # ── 应用 ──
    APP_NAME: str = "server"
    DEBUG: bool = True

    # ── 服务监听 ──
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8089

    # ── MySQL（与金毛大战波斯猫共用一个库，本项目表统一用 hd_ 前缀）──
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "golden_vs_persian"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )

    # ── LINE ──
    # LIFF Channel ID：校验 /api/auth/line 下发的 id_token 的 aud 声明
    LINE_CHANNEL_ID: str = ""

    # ── JWT ──
    JWT_SECRET: str = "please-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 168  # 7 天

    # ── 防刷签名 ──
    # 必须与前端 front/src/api/request.ts 中的 SIGN_SALT 完全一致
    ANTI_CHEAT_SALT: str = "Hd@2026!AntiCheat#7xQz$K9vM"
    ANTI_CHEAT_SKEW_SECONDS: int = 60  # 签名时间戳允许的最大误差（秒）

    # ── Redis ──
    # 统一用分段参数连接，便于切换不同 Redis 提供方（本地 / Upstash / 云厂商）
    REDIS_USERNAME: str = "default"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    # 强制 TLS（rediss://）：其他云 Redis 需要时置 true；
    # Upstash（host 含 .upstash.io）无需配置，代码会自动走 TLS
    REDIS_SSL: bool = False

    # ── 防刷（服务端行为校验） ──
    SESSION_TTL_SECONDS: int = 3600  # 开局会话有效期（1 小时）
    SUBMIT_RATE_LIMIT_PER_MINUTE: int = 3  # 同一用户每分钟最多结算次数
    MIN_CLEAR_TIME_SECONDS: float = 3.0  # 允许的最短通关时间（秒），低于即视为机刷
    CLEAR_TIME_TOLERANCE_SECONDS: float = 5.0  # clear_time 超出理论时间的容忍误差

    # ── 奖励发放（C1：所有"加道具"类奖励的唯一入口 /api/rewards/grant）──
    REWARD_DAILY_CAP_PER_PLACEMENT: int = 10  # 同一渠道（placement）每日发放上限（按 UTC 日）
    REWARD_NONCE_TTL_SECONDS: int = 604800  # 幂等 nonce 去重保留时长（7 天，覆盖活动/补发窗口）

    # ── 排行榜（E2） ──
    LEADERBOARD_CACHE_TTL_SECONDS: int = 60  # 排行榜缓存秒数（新成绩提交会主动失效全国榜）

    # ── 管理后台 ──
    # 运营后台鉴权令牌（X-Admin-Token 请求头）；留空 = 后台整体 403 关闭
    ADMIN_TOKEN: str = ""

    # ── F3 监控告警 ──
    # 单请求耗时超过该毫秒数记慢请求告警；单分钟 5xx 达到该阈值触发错误率告警
    ALERT_SLOW_MS: int = 2000
    ALERT_ERROR_PER_MINUTE: int = 10
    # 可选：群机器人 Webhook（告警时 POST JSON {msg_type:text, text:{content}}）
    ALERT_WEBHOOK_URL: str = ""

    # ── C3 真实支付渠道（占位；未配置时回调返回 501） ──
    # LINE Pay（LINEPay API）渠道凭据，接入需商务资质
    LINE_PAY_CHANNEL_ID: str = ""
    LINE_PAY_CHANNEL_SECRET: str = ""

    # ── H3 版本/强更 ──
    # 兜底最低客户端版本（如 "0.1.0"；空 = 不限制），正式值建议写 hd_configs 下发
    MIN_CLIENT_VER: str = ""

    # ── 阿里云 OSS ──
    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""
    OSS_BUCKET_NAME: str = ""
    OSS_ENDPOINT: str = "https://oss-cn-shanghai.aliyuncs.com/"

    # extra="ignore" — 允许 .env 中存在未声明的运维变量（如 SSH_*、MYSQL_ROOT_*）
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""可选错误监控接入（F3：Sentry）

sentry-sdk 为可选依赖（pyproject optional-dependencies.monitoring）。
配置 SENTRY_DSN 后自动初始化；未安装依赖或初始化失败仅告警，不影响启动。
"""

import logging

from config import get_settings

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    settings = get_settings()
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENV_NAME,
            traces_sample_rate=0.05,  # 只采样 5% 事务，控制成本
            send_default_pii=False,
        )
        logger.info(f"[monitor] Sentry 已启用（environment={settings.ENV_NAME}）")
    except ImportError:
        logger.warning("[monitor] 已配置 SENTRY_DSN 但未安装 sentry-sdk（pip install -e 'server[monitoring]'）")
    except Exception as e:
        logger.warning(f"[monitor] Sentry 初始化失败（忽略）: {e}")

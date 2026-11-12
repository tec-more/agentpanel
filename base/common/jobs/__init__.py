"""平台作业调度（W2-3）。

对外只暴露进程内单例 ``job_scheduler`` 与注册函数；插件作业一律由
``manifest.jobs`` 声明，不在本模块静态导入任何插件实现。
"""
from base.common.jobs.scheduler import (
    PLATFORM_KEY,
    JobScheduler,
    JobSpec,
    job_scheduler,
    register_platform_job,
)

__all__ = [
    "PLATFORM_KEY",
    "JobScheduler",
    "JobSpec",
    "job_scheduler",
    "register_platform_job",
]

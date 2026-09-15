import logging
import os
import threading

from flask import copy_current_request_context

from backend.app.common.exceptions.error_codes import BusinessException, ErrorCode
from backend.app.common.utils.get_random_picture import get_random_bz
from backend.app.common.utils.save_webpage_screenshot import upload_image_to_bed, take_screenshot_and_save

logger = logging.getLogger(__name__)


def generate_app_page_screenshot_and_save_async(app_id: int, app_deploy_url: str) -> None:
    """
    异步非阻塞版本：在 daemon 子线程中依次执行截图、上传、更新数据库、清理临时文件。
    主线程调用后立即返回，不会阻塞主流程。
    内部异常通过 logging 记录，不会影响主业务。

    注意：必须在 Flask 请求上下文中调用（内部需要复制 request context 到子线程）。

    Args:
        app_id: 关联应用 ID
        app_deploy_url: 已部署应用的可访问 URL
    """
    # 复制当前请求上下文到子线程，解决 Flask-SQLAlchemy request-scoped session
    # 在子线程中报 RuntimeError: Working outside of application context 的问题
    @copy_current_request_context
    def _pipeline_with_context():
        _run_screenshot_pipeline(app_id, app_deploy_url)

    thread = threading.Thread(
        target=_pipeline_with_context,
        daemon=True,
    )
    thread.start()
    logger.info(f"截图任务已启动（异步）: app_id={app_id}, url={app_deploy_url}")


def _run_screenshot_pipeline(app_id: int, app_deploy_url: str) -> None:
    """
    截图流水线（线程入口），内部消化所有异常，避免线程崩溃影响进程
    """
    coverage_path = None
    from backend.app.services.app_service import update_app_coverage_svc
    try:
        # 1. 截图
        coverage_path = take_screenshot_and_save(app_deploy_url)
        if not coverage_path:
            logger.error(f"截图失败: app_id={app_id}")
            return

        # 2. 上传图床
        coverage_url = upload_image_to_bed(coverage_path)
        if not coverage_url:
            logger.error(f"上传图床失败: app_id={app_id}, file={coverage_path}")
            return

        # 3. 更新数据库
        update_app_coverage_svc(app_id, coverage_url)
        logger.info(f"截图保存成功: app_id={app_id}, coverage={coverage_url}")

    except Exception as e:
        logger.error(f"截图流水线异常: app_id={app_id}, 错误: {e}\n使用随机图片作为封面")
        coverage_url = get_random_bz()
        update_app_coverage_svc(app_id, coverage_url)
    finally:
        # 4. 清理本地临时文件（无论成功失败都清理）
        if coverage_path and os.path.isfile(coverage_path):
            try:
                os.remove(coverage_path)
            except OSError as e:
                logger.warning(f"清理截图临时文件失败: {coverage_path}, 错误: {e}")


def generate_app_page_screenshot_and_save(app_id: int, app_deploy_url: str):
    """
    生成应用封面截图并将图片 URL 保存到数据库，调用者需保证应用已部署且部署URL已经存在
    """
    from backend.app.services.app_service import update_app_coverage_svc
    try:
        # 生成截图
        coverage_path = take_screenshot_and_save(app_deploy_url)
        if not coverage_path:
            logger.error(f"截图失败: app_id={app_id}")
            raise BusinessException(ErrorCode.INTERNAL_ERROR, "截图失败")
        # 上传图片到图床
        coverage_url = upload_image_to_bed(coverage_path)
        if not coverage_url:
            raise BusinessException(ErrorCode.INTERNAL_ERROR, "上传图片失败")
        # 更新 app 的 app_coverage
        update_app_coverage_svc(app_id, coverage_url)
        # 清理本地文件
        os.remove(coverage_path)
    except Exception as e:
        logging.error(f"截图流水线异常: app_id={app_id}, 错误: {e}")
        # 使用随机图片作为封面
        coverage_url = get_random_bz()
        update_app_coverage_svc(app_id, coverage_url)
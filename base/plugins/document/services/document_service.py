"""
文档管理 Service 层
"""
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from base.common.log import log
from base.common.setting import settings

try:
    from base.plugins.document.models.document_models import (
        DocumentCategory,
        Document,
        DocumentVersion,
        DocumentTag,
    )
    from base.plugins.document.schemas.document_schema import (
        DocumentCategoryCreate,
        DocumentCategoryUpdate,
        DocumentCreate,
        DocumentUpdate,
        DocumentVersionCreate,
        DocumentVersionUpdate,
    )
except ImportError:
    pass


def _get_storage_dir() -> Path:
    """获取文档存储根目录"""
    storage_dir = Path(settings.base_path) / "storage" / "documents"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def _generate_storage_path(file_name: str) -> str:
    """生成文档存储路径 (按年月分目录)"""
    now = datetime.now()
    year_month = now.strftime("%Y/%m")
    storage_dir = _get_storage_dir() / year_month
    storage_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    safe_name = f"{timestamp}_{file_name}"
    target_path = storage_dir / safe_name
    return str(target_path)


def _extract_file_extension(file_name: str) -> Optional[str]:
    """提取文件扩展名"""
    if not file_name:
        return None
    _, ext = os.path.splitext(file_name)
    return ext.lower().lstrip(".") if ext else None


# ==================== 分类服务 ====================

class CategoryService:
    """文档分类管理服务"""

    @staticmethod
    async def get_by_id(category_id: int) -> Optional[DocumentCategory]:
        return await DocumentCategory.filter(id=category_id).first()

    @staticmethod
    async def get_all(
        name: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[DocumentCategory]:
        query = DocumentCategory.all()
        if name:
            query = query.filter(name__icontains=name)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        return await query.order_by("sort", "id")

    @staticmethod
    async def get_tree() -> List[Dict[str, Any]]:
        """获取完整分类树"""
        all_categories = await DocumentCategory.filter(is_active=True).order_by("sort", "id").all()

        def build_tree(parent_id: Optional[int]) -> List[Dict[str, Any]]:
            children = [c for c in all_categories if (c.parent_id or 0) == (parent_id or 0)]
            result = []
            for cat in children:
                item = {
                    "id": cat.id,
                    "name": cat.name,
                    "parent_id": cat.parent_id,
                    "sort": cat.sort,
                    "is_active": cat.is_active,
                    "children": build_tree(cat.id),
                }
                result.append(item)
            return result

        return build_tree(None)

    @staticmethod
    async def create(data: DocumentCategoryCreate) -> DocumentCategory:
        if data.parent_id:
            parent = await DocumentCategory.filter(id=data.parent_id).first()
            if not parent:
                raise ValueError("父分类不存在")
        return await DocumentCategory.create(**data.model_dump(exclude_none=True))

    @staticmethod
    async def update(category_id: int, data: DocumentCategoryUpdate) -> Optional[DocumentCategory]:
        category = await DocumentCategory.filter(id=category_id).first()
        if not category:
            return None
        if data.parent_id and data.parent_id == category_id:
            raise ValueError("不能将分类设为自己的子分类")
        update_data = data.model_dump(exclude_none=True)
        await category.update_from_dict(update_data).save()
        return category

    @staticmethod
    async def delete(category_id: int) -> bool:
        category = await DocumentCategory.filter(id=category_id).first()
        if not category:
            return False
        child_count = await DocumentCategory.filter(parent_id=category_id).count()
        if child_count > 0:
            raise ValueError("该分类下存在子分类，无法删除")
        doc_count = await Document.filter(category_id=category_id).count()
        if doc_count > 0:
            raise ValueError("该分类下存在文档，无法删除")
        deleted = await DocumentCategory.filter(id=category_id).delete()
        return deleted > 0

    @staticmethod
    async def sort_update(ids: List[int]) -> bool:
        """批量更新排序"""
        for idx, cat_id in enumerate(ids):
            cat = await DocumentCategory.filter(id=cat_id).first()
            if cat:
                cat.sort = idx
                await cat.save()
        return True


# ==================== 文档服务 ====================

class DocumentService:
    """通用文档管理服务"""

    @staticmethod
    async def get_by_id(doc_id: int) -> Optional[Document]:
        return await Document.filter(id=doc_id).first()

    @staticmethod
    async def get_list(
        page: int = 1,
        page_size: int = 10,
        title: Optional[str] = None,
        file_name: Optional[str] = None,
        file_type: Optional[str] = None,
        category_id: Optional[int] = None,
        status: Optional[str] = None,
        business_type: Optional[str] = None,
        business_id: Optional[int] = None,
        visibility: Optional[str] = None,
        tag: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[Document], int]:
        query = Document.all()

        # 默认过滤掉已删除的文档
        if not status:
            query = query.filter(status="normal")
        else:
            query = query.filter(status=status)

        if title:
            query = query.filter(title__icontains=title)
        if file_name:
            query = query.filter(file_name__icontains=file_name)
        if file_type:
            query = query.filter(file_type=file_type)
        if category_id:
            query = query.filter(category_id=category_id)
        if business_type:
            query = query.filter(business_type=business_type)
        if business_id:
            query = query.filter(business_id=business_id)
        if visibility:
            query = query.filter(visibility=visibility)
        if tag:
            query = query.filter(tags__contains=[tag])

        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by("-created_at")
        return items, total

    @staticmethod
    async def create_document(
        data: DocumentCreate,
        user_id: Optional[int] = None,
        file_bytes: Optional[bytes] = None
    ) -> Document:
        if file_bytes:
            file_path = _generate_storage_path(data.file_name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            data.file_path = file_path
            data.file_size = data.file_size or len(file_bytes)

        if data.category_id:
            category = await CategoryService.get_by_id(data.category_id)
            if not category:
                raise ValueError("分类不存在")

        doc = await Document.create(
            **data.model_dump(exclude_none=True),
            created_by_id=user_id,
        )

        if file_bytes:
            await DocumentVersion.create(
                document_id=doc.id,
                version=1,
                file_path=doc.file_path,
                file_size=doc.file_size,
                change_log="初始版本",
                created_by_id=user_id,
            )

        log.info(f"文档创建成功: {doc.title} (ID: {doc.id})")
        return doc

    @staticmethod
    async def update_document(
        doc_id: int,
        data: DocumentUpdate,
        user_id: Optional[int] = None
    ) -> Optional[Document]:
        doc = await Document.filter(id=doc_id).first()
        if not doc:
            return None

        if data.category_id:
            category = await CategoryService.get_by_id(data.category_id)
            if not category:
                raise ValueError("分类不存在")

        update_data = data.model_dump(exclude_none=True)
        await doc.update_from_dict(update_data).save()
        return doc

    @staticmethod
    async def soft_delete(doc_id: int) -> bool:
        doc = await Document.filter(id=doc_id).first()
        if not doc:
            return False
        doc.status = "deleted"
        await doc.save()
        log.info(f"文档已软删除: {doc.title} (ID: {doc.id})")
        return True

    @staticmethod
    async def batch_soft_delete(doc_ids: List[int]) -> int:
        deleted = 0
        for doc_id in doc_ids:
            if await DocumentService.soft_delete(doc_id):
                deleted += 1
        return deleted

    @staticmethod
    async def restore(doc_id: int) -> bool:
        doc = await Document.filter(id=doc_id).first()
        if not doc:
            return False
        if doc.status != "deleted":
            raise ValueError("该文档不在回收站中")
        doc.status = "normal"
        await doc.save()
        log.info(f"文档已恢复: {doc.title} (ID: {doc.id})")
        return True

    @staticmethod
    async def batch_restore(doc_ids: List[int]) -> int:
        restored = 0
        for doc_id in doc_ids:
            try:
                if await DocumentService.restore(doc_id):
                    restored += 1
            except ValueError:
                pass
        return restored

    @staticmethod
    async def permanent_delete(doc_id: int) -> bool:
        """永久删除文档（物理删除文件和记录）"""
        doc = await Document.filter(id=doc_id).first()
        if not doc:
            return False

        versions = await DocumentVersion.filter(document_id=doc_id).all()
        for ver in versions:
            if ver.file_path and os.path.exists(ver.file_path):
                try:
                    os.remove(ver.file_path)
                except OSError:
                    pass

        if doc.file_path and os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except OSError:
                pass

        deleted = await Document.filter(id=doc_id).delete()
        return deleted > 0

    @staticmethod
    async def move_to_category(
        doc_id: int,
        target_category_id: Optional[int]
    ) -> Optional[Document]:
        doc = await Document.filter(id=doc_id).first()
        if not doc:
            return None
        if target_category_id:
            category = await CategoryService.get_by_id(target_category_id)
            if not category:
                raise ValueError("目标分类不存在")
        doc.category_id = target_category_id
        await doc.save()
        return doc

    @staticmethod
    async def get_by_business(
        business_type: str,
        business_id: int
    ) -> List[Document]:
        return await Document.filter(
            business_type=business_type,
            business_id=business_id,
            status="normal"
        ).order_by("-created_at")

    @staticmethod
    async def get_trash_list(
        page: int = 1,
        page_size: int = 10,
        title: Optional[str] = None,
    ) -> Tuple[List[Document], int]:
        query = Document.filter(status="deleted")
        if title:
            query = query.filter(title__icontains=title)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by("-updated_at")
        return items, total

    @staticmethod
    async def get_statistics() -> Dict[str, Any]:
        total_count = await Document.filter(status="normal").count()
        trash_count = await Document.filter(status="deleted").count()
        archived_count = await Document.filter(status="archived").count()
        categories_count = await DocumentCategory.filter(is_active=True).count()

        type_dist = {}
        try:
            from tortoise.expressions import RawSQL
            docs = await Document.filter(status="normal").all()
            for doc in docs:
                ft = doc.file_type or "other"
                type_dist[ft] = type_dist.get(ft, 0) + 1
        except Exception:
            pass

        return {
            "total_count": total_count,
            "trash_count": trash_count,
            "archived_count": archived_count,
            "categories_count": categories_count,
            "type_distribution": type_dist,
        }


# ==================== 版本服务 ====================

class VersionService:
    """文档版本管理服务"""

    @staticmethod
    async def get_by_id(version_id: int) -> Optional[DocumentVersion]:
        return await DocumentVersion.filter(id=version_id).first()

    @staticmethod
    async def get_by_document(
        document_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[DocumentVersion], int]:
        query = DocumentVersion.filter(document_id=document_id)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by("-version")
        return items, total

    @staticmethod
    async def create_version(
        document_id: int,
        data: DocumentVersionCreate,
        user_id: Optional[int] = None
    ) -> DocumentVersion:
        doc = await Document.filter(id=document_id).first()
        if not doc:
            raise ValueError("文档不存在")

        max_version = await DocumentVersion.filter(document_id=document_id).order_by("-version").first()
        next_version = (max_version.version if max_version else 0) + 1

        version = await DocumentVersion.create(
            document_id=document_id,
            version=next_version,
            file_path=data.file_path,
            file_size=data.file_size,
            change_log=data.change_log,
            created_by_id=user_id,
        )

        doc.version = next_version
        doc.file_path = data.file_path
        doc.file_size = data.file_size
        await doc.save()

        log.info(f"文档新版本: {doc.title} v{next_version}")
        return version

    @staticmethod
    async def update_version(
        version_id: int,
        data: DocumentVersionUpdate
    ) -> Optional[DocumentVersion]:
        version = await DocumentVersion.filter(id=version_id).first()
        if not version:
            return None
        update_data = data.model_dump(exclude_none=True)
        await version.update_from_dict(update_data).save()
        return version

    @staticmethod
    async def rollback(
        document_id: int,
        target_version_id: int,
        change_log: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Optional[DocumentVersion]:
        doc = await Document.filter(id=document_id).first()
        if not doc:
            return None

        target_version = await DocumentVersion.filter(id=target_version_id).first()
        if not target_version or target_version.document_id != document_id:
            raise ValueError("目标版本不存在")

        new_version_data = DocumentVersionCreate(
            file_path=target_version.file_path,
            file_size=target_version.file_size,
            change_log=change_log or f"回滚到版本 v{target_version.version}",
        )
        return await VersionService.create_version(document_id, new_version_data, user_id)

    @staticmethod
    async def delete_version(version_id: int) -> bool:
        version = await DocumentVersion.filter(id=version_id).first()
        if not version:
            return False

        doc = await Document.filter(id=version.document_id).first()
        if doc and doc.version == version.version:
            raise ValueError("不能删除当前版本")

        deleted = await DocumentVersion.filter(id=version_id).delete()
        return deleted > 0

    @staticmethod
    async def upload_new_version(
        document_id: int,
        file_bytes: bytes,
        file_name: str,
        change_log: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Tuple[DocumentVersion, Document]:
        """上传文件创建新版本"""
        doc = await Document.filter(id=document_id).first()
        if not doc:
            raise ValueError("文档不存在")

        # 生成存储路径
        file_ext = _extract_file_extension(file_name)
        storage_path = _generate_storage_path(file_name)
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, "wb") as f:
            f.write(file_bytes)

        # 创建版本记录
        max_version = await DocumentVersion.filter(document_id=document_id).order_by("-version").first()
        next_version = (max_version.version if max_version else 0) + 1

        version = await DocumentVersion.create(
            document_id=document_id,
            version=next_version,
            file_path=storage_path,
            file_size=len(file_bytes),
            change_log=change_log or f"上传新版本 v{next_version}",
            created_by_id=user_id,
        )

        # 更新文档当前版本
        doc.version = next_version
        doc.file_name = file_name
        doc.file_type = file_ext
        doc.file_path = storage_path
        doc.file_size = len(file_bytes)
        await doc.save()

        log.info(f"文档新版本上传: {doc.title} v{next_version}")
        return version, doc


# ==================== 预览服务 ====================

class PreviewService:
    """文档预览服务"""

    PREVIEWABLE_TYPES = {
        "pdf", "txt", "md", "markdown",
        "png", "jpg", "jpeg", "gif", "bmp", "svg", "webp",
        "mp4", "webm", "ogg", "mp3", "wav",
    }

    OFFICE_TYPES = {"doc", "docx", "xls", "xlsx", "ppt", "pptx"}

    @staticmethod
    def is_previewable(file_type: str) -> bool:
        return file_type.lower() in PreviewService.PREVIEWABLE_TYPES

    @staticmethod
    def is_office_file(file_type: str) -> bool:
        return file_type.lower() in PreviewService.OFFICE_TYPES

    @staticmethod
    def get_preview_content_type(file_type: str) -> str:
        """获取预览时的 Content-Type"""
        content_types = {
            "pdf": "application/pdf",
            "txt": "text/plain",
            "md": "text/markdown",
            "markdown": "text/markdown",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "bmp": "image/bmp",
            "svg": "image/svg+xml",
            "webp": "image/webp",
            "mp4": "video/mp4",
            "webm": "video/webm",
            "ogg": "video/ogg",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
        }
        return content_types.get(file_type.lower(), "application/octet-stream")

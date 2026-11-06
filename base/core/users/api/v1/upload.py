"""
文件上传 API
"""
import os
import uuid
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import FileResponse

from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse
from base.common.setting import settings

router = APIRouter(prefix="/v1/upload", tags=["文件上传"])

# 确保上传目录存在
UPLOAD_DIR = Path(settings.base_path) / "uploads" / "images"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 允许的图片格式
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp"
}

# 文件大小限制 (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


def get_file_extension(content_type: str) -> str:
    """根据 Content-Type 获取文件扩展名"""
    extension_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp"
    }
    return extension_map.get(content_type, ".jpg")


@router.post("/image", summary="上传图片")
async def upload_image(
    file: UploadFile = File(...),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    上传图片
    """
    try:
        # 检查文件类型
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            return ErrorResponse(
                msg=f"不支持的文件类型: {file.content_type}，请上传 JPG、PNG、GIF、WebP、BMP 格式的图片",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # 读取文件内容检查大小
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            return ErrorResponse(
                msg="文件大小超过限制 (最大 10MB)",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # 生成唯一文件名
        file_ext = get_file_extension(file.content_type)
        file_name = f"{uuid.uuid4()}{file_ext}"
        
        # 按日期分组存储
        date_dir = datetime.now().strftime("%Y/%m/%d")
        save_dir = UPLOAD_DIR / date_dir
        save_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = save_dir / file_name
        
        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # 返回可访问的 URL
        file_url = f"/uploads/images/{date_dir}/{file_name}"
        
        return SuccessResponse(
            data={
                "url": file_url,
                "filename": file_name,
                "size": len(file_content),
                "content_type": file.content_type
            },
            msg="上传成功"
        )
        
    except Exception as e:
        return ErrorResponse(
            msg=f"上传失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/images/{year}/{month}/{day}/{filename}", summary="访问上传的图片")
async def get_uploaded_image(year: str, month: str, day: str, filename: str):
    """
    访问上传的图片
    """
    file_path = UPLOAD_DIR / year / month / day / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
    
    # 根据文件扩展名确定 Content-Type
    ext = file_path.suffix.lower()
    content_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp"
    }
    content_type = content_type_map.get(ext, "image/jpeg")
    
    return FileResponse(file_path, media_type=content_type)


AUDIO_UPLOAD_DIR = Path(settings.base_path) / "uploads" / "audio"
AUDIO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/audio/{year}/{month}/{day}/{filename}", summary="访问上传的音频")
async def get_uploaded_audio(year: str, month: str, day: str, filename: str):
    """
    访问上传的音频文件
    """
    file_path = AUDIO_UPLOAD_DIR / year / month / day / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")
    
    ext = file_path.suffix.lower()
    content_type_map = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".aac": "audio/aac"
    }
    content_type = content_type_map.get(ext, "audio/mpeg")
    
    return FileResponse(file_path, media_type=content_type)

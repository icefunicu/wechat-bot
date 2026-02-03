import os
import io
import base64
import logging
from PIL import Image

def process_image_for_api(image_path: str, max_size: int = 1024, max_file_size_kb: int = 500) -> str:
    """
    处理图片以适应 API 要求：
    1. 调整尺寸（最大边长限制）
    2. 压缩质量
    3. 转 Base64
    
    Args:
        image_path: 图片路径
        max_size: 最大边长（像素）
        max_file_size_kb: 最大文件大小（KB），超过会尝试降低质量
        
    Returns:
        Base64 编码的字符串
    """
    try:
        with Image.open(image_path) as img:
            # 1. 转换为 RGB (处理 PNG 透明通道等)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # 2. 调整尺寸
            width, height = img.size
            if max(width, height) > max_size:
                ratio = max_size / max(width, height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 3. 压缩并转字节流
            quality = 90
            buffer = io.BytesIO()
            while quality > 20:
                buffer.seek(0)
                buffer.truncate()
                img.save(buffer, format="JPEG", quality=quality)
                if buffer.tell() / 1024 <= max_file_size_kb:
                    break
                quality -= 10
            
            # 4. 转 Base64
            buffer.seek(0)
            base64_str = base64.b64encode(buffer.read()).decode('utf-8')
            return base64_str
            
    except Exception as e:
        logging.error(f"Image processing failed for {image_path}: {e}")
        # 降级：尝试直接读取原文件（如果处理失败）
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            return ""

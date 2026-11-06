"""
音频格式检测和转换工具
支持Float32到Int16 PCM的转换
"""
import struct
import logging

logger = logging.getLogger(__name__)


def detect_audio_format(data: bytes, filename: str = "") -> dict:
    """
    检测音频数据格式

    Args:
        data: 音频数据
        filename: 文件名

    Returns:
        格式信息字典
    """
    result = {
        'format': 'unknown',  # unknown, wav, pcm_int16, pcm_float32
        'confidence': 0.0,
        'sample_rate': 16000,
        'channels': 1,
        'bits': 16
    }

    # 检查WAV头
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        result['format'] = 'wav'
        result['confidence'] = 1.0
        logger.info(f"[格式检测] 检测到WAV格式")
        return result

    # 检测Float32 vs Int16
    if len(data) >= 4:
        # 检查前几个字节是否看起来像Float32
        # Float32的典型特征：某些字节模式
        try:
            # 尝试解析为Float32
            float32_value = struct.unpack('<f', data[:4])[0]
            is_float32 = -1.0 <= float32_value <= 1.0

            # 检查前4个样本
            if is_float32 and len(data) >= 16:
                float32_samples = struct.unpack('<4f', data[:16])
                all_in_range = all(-1.0 <= s <= 1.0 for s in float32_samples)

                if all_in_range:
                    result['format'] = 'pcm_float32'
                    result['confidence'] = 0.9
                    logger.info(f"[格式检测] 检测到Float32 PCM格式")
                    logger.info(f"[格式检测] 前4个样本: {float32_samples}")
                    return result

        except:
            pass

        # 如果不是Float32，假设是Int16 PCM
        result['format'] = 'pcm_int16'
        result['confidence'] = 0.5
        logger.info(f"[格式检测] 假设为Int16 PCM格式")

    return result


def convert_float32_to_int16_pcm(float32_data: bytes) -> bytes:
    """
    将Float32 PCM数据转换为Int16 PCM格式

    Args:
        float32_data: Float32格式的PCM数据（-1.0到1.0）

    Returns:
        Int16格式的PCM数据（-32768到32767）
    """
    logger.info(f"[格式转换] Float32 → Int16 PCM: {len(float32_data)} bytes")

    # 计算样本数
    num_samples = len(float32_data) // 4

    # 解析Float32样本
    float32_samples = struct.unpack(f'<{num_samples}f', float32_data)

    # 转换为Int16
    int16_samples = []
    clipped_count = 0

    for i, sample in enumerate(float32_samples):
        # 限制范围
        if sample > 1.0:
            sample = 1.0
            clipped_count += 1
        elif sample < -1.0:
            sample = -1.0
            clipped_count += 1

        # 转换为Int16
        int16_value = int(sample * 32767.0)
        int16_samples.append(int16_value)

    # 编码为Int16字节（Little-endian）
    int16_data = struct.pack(f'<{num_samples}h', *int16_samples)

    logger.info(f"[格式转换] 转换完成: {len(int16_data)} bytes")
    if clipped_count > 0:
        logger.warning(f"[格式转换] {clipped_count}/{num_samples} 样本被限幅")

    return int16_data


def convert_audio_to_wav(
    data: bytes,
    filename: str = "",
    sample_rate: int = 16000,
    channels: int = 1,
    bits: int = 16
) -> tuple[bytes, dict]:
    """
    智能转换音频到WAV格式
    支持自动检测Float32并转换

    Args:
        data: 音频数据
        filename: 文件名
        sample_rate: 采样率
        channels: 声道数
        bits: 位深度

    Returns:
        (wav_data, info)
    """
    info = {
        'original_size': len(data),
        'original_format': 'unknown',
        'converted': False,
        'final_format': 'wav',
        'final_size': 0
    }

    # 检测格式
    format_detection = detect_audio_format(data, filename)
    info['original_format'] = format_detection['format']

    logger.info(f"[音频处理] 检测到格式: {format_detection['format']}")

    # 如果已经是WAV，直接返回
    if format_detection['format'] == 'wav':
        logger.info(f"[音频处理] 已经是WAV格式，无需转换")
        info['final_size'] = len(data)
        return data, info

    # 根据格式处理
    pcm_data = data

    # 如果是Float32，先转换为Int16 PCM
    if format_detection['format'] == 'pcm_float32':
        logger.info(f"[音频处理] 检测到Float32，转换为Int16 PCM")
        pcm_data = convert_float32_to_int16_pcm(data)
        info['converted'] = True

    # 添加WAV头
    from .pcm_utils import PCMUtils
    wav_data = PCMUtils.pcm_to_wav(
        pcm_data,
        sample_rate=sample_rate,
        num_channels=channels,
        sampwidth=bits // 8
    )

    info['final_size'] = len(wav_data)
    info['converted'] = True

    logger.info(f"[音频处理] WAV文件生成完成: {info['final_size']} bytes")

    return wav_data, info


# 导出
__all__ = ['detect_audio_format', 'convert_float32_to_int16_pcm', 'convert_audio_to_wav']

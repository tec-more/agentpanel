"""
PCM音频处理工具
将原始PCM数据封装为WAV格式
"""
import struct
import io
import wave
import logging

logger = logging.getLogger(__name__)


class PCMUtils:
    """PCM音频处理工具类"""

    @staticmethod
    def pcm_to_wav(
        pcm_data: bytes,
        sample_rate: int = 16000,
        num_channels: int = 1,
        sampwidth: int = 2,
        audio_format: str = "PCM_16"
    ) -> bytes:
        """
        将原始PCM数据封装为WAV格式

        Args:
            pcm_data: 原始PCM数据
            sample_rate: 采样率 (默认16000)
            num_channels: 声道数 (默认1=单声道)
            sampwidth: 采样宽度，单位字节 (默认2=16bit)
            audio_format: 音频格式标识

        Returns:
            WAV格式的字节数据
        """
        logger.info(f"[PCM] 开始转换: {len(pcm_data)} bytes PCM → WAV")
        logger.info(f"[PCM] WAV头参数: sample_rate={sample_rate}Hz, channels={num_channels}, sampwidth={sampwidth} ({sampwidth*8}bit)")

        # 创建WAV文件
        output = io.BytesIO()

        with wave.open(output, 'wb') as wav_file:
            # 设置音频参数
            wav_file.setnchannels(num_channels)
            wav_file.setsampwidth(sampwidth)
            wav_file.setframerate(sample_rate)

            # 写入PCM数据
            wav_file.writeframes(pcm_data)

        wav_data = output.getvalue()
        logger.info(f"[PCM] 转换完成: {len(wav_data)} bytes WAV")

        return wav_data

    @staticmethod
    def detect_pcm_format(data: bytes, filename: str = "") -> dict:
        """
        检测PCM数据的格式参数

        Args:
            data: 音频数据
            filename: 文件名（可能包含格式信息）

        Returns:
            格式信息字典（只检测是否为PCM，不推算采样率）
        """
        logger.info(f"[PCM] 检测音频格式: {len(data)} bytes")

        result = {
            'is_pcm': False,
            'confidence': 0.0
        }

        # 方法1: 检查文件扩展名
        if filename:
            fname_lower = filename.lower()
            if fname_lower.endswith('.pcm'):
                result['is_pcm'] = True
                result['confidence'] += 0.5
                logger.info(f"[PCM] 文件名提示: .pcm格式")

        # 方法2: 检查是否是WAV文件（有RIFF头）
        if len(data) >= 12:
            # 检查RIFF头
            if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
                logger.info(f"[PCM] 检测到WAV文件头，不是纯PCM")
                result['is_pcm'] = False
                return result

        # 方法3: 如果没有WAV头，很可能是PCM
        if len(data) > 44 and data[:4] != b'RIFF':
            result['is_pcm'] = True
            result['confidence'] += 0.8
            logger.info(f"[PCM] 无WAV文件头，判断为PCM数据")

        logger.info(f"[PCM] 检测结果: is_pcm={result['is_pcm']}, confidence={result['confidence']}")
        return result

    @staticmethod
    def add_wav_header(
        pcm_data: bytes,
        num_channels: int = 1,
        sample_rate: int = 16000,
        bits_per_sample: int = 16
    ) -> bytes:
        """
        手动添加WAV文件头（不使用wave库）

        WAV文件结构:
        - RIFF header (12 bytes)
        - fmt chunk (24 bytes)
        - data chunk header (8 bytes)
        - actual data

        Args:
            pcm_data: PCM数据
            num_channels: 声道数
            sample_rate: 采样率
            bits_per_sample: 位深度

        Returns:
            完整的WAV文件数据
        """
        logger.info(f"[PCM] 手动添加WAV头: {len(pcm_data)} bytes")

        # 计算参数
        byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
        block_align = num_channels * (bits_per_sample // 8)
        data_size = len(pcm_data)
        file_size = data_size + 36  # 36 = 头部大小

        # 构建WAV头
        header = b''

        # RIFF header (12 bytes)
        header += b'RIFF'  # ChunkID
        header += struct.pack('<I', file_size)  # ChunkSize
        header += b'WAVE'  # Format

        # fmt chunk (24 bytes)
        header += b'fmt '  # Subchunk1ID (注意空格)
        header += struct.pack('<I', 16)  # Subchunk1Size (16 for PCM)
        header += struct.pack('<H', 1)  # AudioFormat (1 = PCM)
        header += struct.pack('<H', num_channels)  # NumChannels
        header += struct.pack('<I', sample_rate)  # SampleRate
        header += struct.pack('<I', byte_rate)  # ByteRate
        header += struct.pack('<H', block_align)  # BlockAlign
        header += struct.pack('<H', bits_per_sample)  # BitsPerSample

        # data chunk header (8 bytes)
        header += b'data'  # Subchunk2ID
        header += struct.pack('<I', data_size)  # Subchunk2Size

        # 组合完整WAV文件
        wav_data = header + pcm_data

        logger.info(f"[PCM] WAV头添加完成: {len(wav_data)} bytes (头: {len(header)}, 数据: {data_size})")

        return wav_data


def convert_pcm_to_wav(
    data: bytes,
    filename: str = "",
    sample_rate: int = 16000,
    channels: int = 1,
    bits: int = 16
) -> tuple[bytes, dict]:
    """
    智能转换PCM到WAV

    自动检测是否为PCM，如果是则转换

    Args:
        data: 音频数据
        filename: 文件名
        sample_rate: 采样率
        channels: 声道数
        bits: 位深度

    Returns:
        (wav_data, info) 转换后的数据和信息
    """
    info = {
        'original_size': len(data),
        'converted': False,
        'format': 'unknown'
    }

    # 检测格式
    detection = PCMUtils.detect_pcm_format(data, filename)

    if not detection['is_pcm']:
        # 已经是WAV格式
        info['format'] = 'wav'
        logger.info(f"[PCM] 数据已是WAV格式，无需转换")
        return data, info

    # 是PCM格式，需要转换
    logger.info(f"[PCM] 检测到PCM数据，开始转换...")
    logger.info(f"[PCM] 使用参数: rate={sample_rate}, channels={channels}, bits={bits}")

    # 计算预期时长（帮助调试）
    expected_duration = len(data) / (sample_rate * channels * (bits // 8))
    logger.info(f"[PCM] 数据大小: {len(data)} bytes, 预期时长: {expected_duration:.2f}秒")

    try:
        wav_data = PCMUtils.pcm_to_wav(
            data,
            sample_rate=sample_rate,
            num_channels=channels,
            sampwidth=bits // 8
        )

        info['converted'] = True
        info['format'] = 'wav'
        info['final_size'] = len(wav_data)
        info['parameters'] = {
            'sample_rate': sample_rate,
            'channels': channels,
            'bits': bits
        }

        return wav_data, info

    except Exception as e:
        logger.error(f"[PCM] 转换失败: {e}")
        # 转换失败，返回原数据
        return data, info


# 导出函数
__all__ = ['PCMUtils', 'convert_pcm_to_wav']

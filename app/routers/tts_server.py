# -*- coding: utf-8 -*-
"""
离线中文TTS API服务（基于MeloTTS）
专为ARM架构CPU优化，适合树莓派等设备
"""

import os
import logging
import uuid
import io
import wave
import asyncio
import argparse
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, status, Response
from pydantic import BaseModel
from typing import Optional
import time
import subprocess
import sys
import torch
import tempfile

# 关闭 Hugging Face 联网功能
# os.environ["HF_HUB_OFFLINE"] = "1"        # 禁用从 Hugging Face Hub 下载
# os.environ["TRANSFORMERS_OFFLINE"] = "1"  # 禁用 Transformers 库的联网
# os.environ["DATASETS_OFFLINE"] = "1"      # 禁用 Datasets 库的联网
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tts_api")

# 创建线程池（TTS是CPU密集型）
executor = ThreadPoolExecutor(max_workers=2)

# 创建路由器
router = APIRouter(
    prefix="/tts",
    tags=["TTS"],
)



# ========== 命令行参数解析 ==========
def parse_args():
    parser = argparse.ArgumentParser(description="TTS Service API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8880, help="Port to bind the server to")
    parser.add_argument("--device", default="cpu", choices=["auto", "cpu", "cuda", "cuda:0", "mps"],
                        help="Device to run the TTS model on")
    parser.add_argument("--sample-rate", type=int, default=22050, help="Sample rate for audio output")
    parser.add_argument("--max-text-length", type=int, default=500, help="Maximum allowed text length")
    parser.add_argument("--language", default="ZH", help="Default language for TTS")
    parser.add_argument("--config-path", default="/app/models/all-MiniLM-L6-v2/config.json", help="Path to custom config file")
    parser.add_argument("--ckpt-path", default="/app/models/all-MiniLM-L6-v2/checkpoint.pth", help="Path to custom checkpoint file")
    return parser.parse_args()

# 解析命令行参数
args = parse_args()

# ========== 全局配置 ==========
SAMPLE_RATE = args.sample_rate
DEFAULT_MODEL = "MeloTTS"
LANGUAGE = args.language
DEVICE = args.device
SPEED = 1.0
MAX_TEXT_LENGTH = args.max_text_length


# ========== 依赖检查与安装 ==========
def check_and_install_dependencies():
    """检查并安装必要的依赖"""
    missing_deps = []

    # 检查必要的依赖
    try:
        import melo
    except ImportError:
        missing_deps.append("melo-tts")

    try:
        import pydub
    except ImportError:
        missing_deps.append("pydub")

    # 安装缺失的依赖
    if missing_deps:
        logger.warning(f"Missing dependencies: {missing_deps}. Installing...")
        try:
            # 使用subprocess安装依赖
            for dep in missing_deps:
                subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            logger.info("Dependencies installed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to install dependencies: {str(e)}")
            return False

    return True


# 检查并安装依赖
dependencies_ok = check_and_install_dependencies()


# ========== 模型加载 ==========
def initialize_tts():
    """初始化MeloTTS引擎"""
    if not dependencies_ok:
        logger.error("Dependencies not available, cannot initialize TTS")
        return None

    try:
        logger.info("Loading MeloTTS model...")

        # 动态导入MeloTTS
        from melo.api import TTS

        # 创建TTS实例
        tts = TTS(language='ZH', device=DEVICE,config_path=args.config_path,ckpt_path=args.ckpt_path)

        logger.info("MeloTTS model loaded successfully")
        return tts
    except Exception as e:
        logger.error(f"Failed to load MeloTTS model: {str(e)}")
        return None


# 全局TTS实例
tts_instance = None


def get_tts_instance():
    """获取或初始化TTS实例"""
    global tts_instance
    if tts_instance is None:
        tts_instance = initialize_tts()
    return tts_instance


# ========== 请求模型 ==========
class TTSPayload(BaseModel):
    text: str
    user: str
    format: Optional[str] = "wav"  # 输出格式: wav 或 mp3


# ========== 工具函数 ==========
def generate_tts_audio(text: str):
    """同步生成TTS音频"""
    try:
        # 获取TTS实例
        tts = get_tts_instance()
        if not tts:
            return None

        # 获取说话人ID
        speaker_ids = tts.hps.data.spk2id
        speaker_id = speaker_ids[LANGUAGE]

        # 使用临时文件保存音频
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = temp_file.name

        # 生成TTS音频到文件
        start_time = time.time()
        tts.tts_to_file(text, speaker_id, temp_path, speed=SPEED)
        end_time = time.time()

        logger.info(f"TTS generation took {end_time - start_time:.2f} seconds")

        # 读取生成的音频文件
        with open(temp_path, 'rb') as f:
            audio_data = f.read()

        # 清理临时文件
        os.unlink(temp_path)

        return audio_data

    except Exception as e:
        logger.error(f"TTS generation error: {str(e)}")
        return None


def wav_to_mp3(wav_data: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """将WAV转换为MP3"""
    try:
        from pydub import AudioSegment
        import io

        # 从WAV数据创建音频段
        audio = AudioSegment.from_wav(io.BytesIO(wav_data))

        # 转换为MP3
        mp3_io = io.BytesIO()
        audio.export(mp3_io, format="mp3", bitrate="32k")

        return mp3_io.getvalue()
    except ImportError:
        logger.warning("pydub not available, MP3 conversion disabled")
        return None
    except Exception as e:
        logger.error(f"MP3 conversion failed: {str(e)}")
        return None


# ========== 路由接口 ==========
@router.post("/text-to-audio")
async def text_to_audio(payload: TTSPayload):
    """生成TTS音频"""
    if not dependencies_ok:
        raise HTTPException(
            status_code=503,
            detail="TTS service unavailable: Required dependencies not installed"
        )

    text = payload.text.strip()
    user = payload.user
    format = payload.format.lower()

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Text too long (max {MAX_TEXT_LENGTH} chars)"
        )

    logger.info(f"[TTS] User: {user}, Text: {text[:30]}..., Format: {format}")

    try:
        # 在线程中运行TTS（CPU密集型）
        loop = asyncio.get_event_loop()
        audio_data = await loop.run_in_executor(
            executor,
            generate_tts_audio,
            text
        )

        if audio_data is None:
            raise HTTPException(status_code=500, detail="TTS generation failed")

        # 如果需要MP3格式
        if format == "mp3":
            mp3_data = wav_to_mp3(audio_data, SAMPLE_RATE)
            if mp3_data:
                filename = f"tts_{uuid.uuid4().hex}.mp3"
                return Response(
                    content=mp3_data,
                    media_type="audio/mpeg",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "X-Sample-Rate": str(SAMPLE_RATE),
                        "X-Model": DEFAULT_MODEL,
                        "X-Format": "mp3"
                    }
                )
            else:
                # 如果MP3转换失败，返回WAV
                logger.warning("MP3 conversion failed, falling back to WAV")
                format = "wav"

        # 默认返回WAV
        if format == "wav":
            filename = f"tts_{uuid.uuid4().hex}.wav"
            return Response(
                content=audio_data,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-Sample-Rate": str(SAMPLE_RATE),
                    "X-Model": DEFAULT_MODEL,
                    "X-Format": "wav"
                }
            )

        # 未知格式
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    except Exception as e:
        logger.error(f"[TTS Error] {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")


@router.get("/voices")
async def list_voices():
    """返回可用的语音模型和说话人列表"""
    tts = get_tts_instance()
    speaker_ids = tts.hps.data.spk2id if tts else {}

    return {
        "models": [
            {
                "id": DEFAULT_MODEL,
                "name": "中文TTS模型(MeloTTS)",
                "description": "基于MeloTTS的中文TTS模型",
                "sample_rate": SAMPLE_RATE,
                "language": LANGUAGE
            }
        ],
        "speakers": [{"id": k, "name": k} for k in speaker_ids.keys()],
        "default_model": DEFAULT_MODEL,
        "engine": "melo-tts",
        "offline": True,
        "sample_rate": SAMPLE_RATE,
        "dependencies_ok": dependencies_ok
    }


@router.get("/health")
async def health():
    """健康检查"""
    # 检查TTS实例是否已初始化
    tts_ready = tts_instance is not None

    return {
        "status": "ok" if tts_ready else "initializing",
        "service": "Offline TTS API (MeloTTS)",
        "engine": "melo-tts",
        "model_loaded": tts_ready,
        "default_model": DEFAULT_MODEL,
        "sample_rate": SAMPLE_RATE,
        "offline": True,
        "dependencies_ok": dependencies_ok,
        "active_tasks": executor._work_queue.qsize() if hasattr(executor, '_work_queue') else 0,
        "arm_compatible": True,
        "message": "Model is loading..." if not tts_ready else "Service is ready"
    }


@router.get("/")
async def root():
    return await health()


# ========== 独立运行支持 ==========
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI(
        title="Offline TTS API",
        description="离线中文TTS服务，基于MeloTTS模型",
        version="1.0.0"
    )

    app.include_router(router)

    logger.info(f"�� Starting Offline TTS API Server on http://0.0.0.0:{args.port}")
    logger.info(f"🔊 Using MeloTTS for Chinese TTS")

    # 检查依赖
    if not dependencies_ok:
        logger.error("❌ Required dependencies are missing. Service may not work properly.")

    # 预加载模型
    logger.info("⏳ Pre-loading TTS model...")
    try:
        get_tts_instance()
        logger.info("✅ Model loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {str(e)}")

    # ARM优化：降低uvicorn工作进程数
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=1,  # ARM设备通常单核，使用单worker
        loop="asyncio"
    )

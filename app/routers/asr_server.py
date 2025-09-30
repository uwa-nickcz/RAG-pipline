# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/30 16:22
# @File     : asr_server.py
# @contact  ： ***
# routers/asr_server.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import os
from funasr import AutoModel
import librosa
import soundfile as sf
import io

router = APIRouter(prefix="/asr", tags=["语音识别"])
from config import model_cache_path
model = None

@router.on_event("startup")
async def startup_event():
    global asrmodel
    print("正在加载语音识别模型...")
    asrmodel = AutoModel(
        punc_model=model_cache_path + r"/models/iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        vad_model=model_cache_path + r"/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        model=model_cache_path + r"/models/iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        disable_update=True,
        device='cpu'
        
    )
    print("模型加载完成")


@router.post("/audio-to-text", summary="语音识别")
async def speech_recognition(
        file: UploadFile = File(..., description="音频文件，字段名必须为'file'"),  # 修改字段名为file
        user: str = Form(None),  # 新增user参数
        hotword: str = Form("魔搭"),
        batch_size_s: int = Form(300)
):
    try:
        # 直接处理上传的字节流，无需临时文件
        audio_bytes = await file.read()

        # 统一转换为WAV格式处理
        if file.filename.lower().endswith('.mp3'):
            # 将MP3转换为WAV
            audio_data, sample_rate = librosa.load(io.BytesIO(audio_bytes), sr=None, mono=True)
            wav_buffer = io.BytesIO()
            sf.write(wav_buffer, audio_data, sample_rate, format='WAV')
            audio_bytes = wav_buffer.getvalue()

        # 创建临时文件处理
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file_path = tmp_file.name

        # 调用模型生成
        res = asrmodel.generate(
            input=tmp_file_path,
            batch_size_s=batch_size_s,
            hotword=hotword
        )

        # 清理临时文件
        os.unlink(tmp_file_path)

        if isinstance(res, list) and len(res) > 0:
            result_text = res[0].get('text', '') if isinstance(res[0], dict) else str(res[0])
            return JSONResponse(content={
                "success": True,
                "text": result_text,  # 确保响应包含text字段
                "hotword": hotword,
                "detail": res
            })
        else:
            return JSONResponse(content={
                "success": False,
                "text": "",
                "message": "识别失败"
            })

    except Exception as e:
        # 异常处理中确保清理临时文件
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        raise HTTPException(status_code=500, detail=f"处理音频文件时出错: {str(e)}")


@router.post("/audio/transcriptions",
             summary="语音识别(OpenAI兼容API)",
             response_description="语音识别结果")
async def openai_style_speech_recognition(
        file: UploadFile = File(..., description="要转录的音频文件，支持WAV/MP3格式"),
        model: str = Form("funasr", description="使用的模型ID(兼容参数)"),
        language: str = Form(None, description="音频语言代码(如'zh')"),
        prompt: str = Form(None, description="上下文提示文本"),
        response_format: str = Form("json", description="响应格式(json/text/srt/vtt)"),
        temperature: float = Form(0.0, description="采样温度"),
        # 您的自定义参数（作为扩展）
        user: str = Form(None, description="用户标识"),
        hotword: str = Form("魔搭", description="热词增强"),
        batch_size_s: int = Form(300, description="批量处理大小(秒)")
):
    """
    OpenAI风格的语音识别端点，支持标准参数和自定义扩展

    兼容参数:
    - file: 音频文件(必须)
    - model: 模型ID(在OpenAI API中必须，此处保留但可选)
    - language: 语言代码
    - prompt: 上下文提示
    - response_format: 响应格式(json/text/srt/vtt)
    - temperature: 采样温度

    扩展参数:
    - user: 用户标识
    - hotword: 热词增强
    - batch_size_s: 批处理大小
    """
    try:
        # 读取音频数据
        audio_bytes = await file.read()

        # 音频格式转换（统一为WAV）
        if file.filename.lower().endswith(('.mp3', '.m4a', '.flac')):
            audio_data, sample_rate = librosa.load(
                io.BytesIO(audio_bytes),
                sr=None,
                mono=True
            )
            wav_buffer = io.BytesIO()
            sf.write(wav_buffer, audio_data, sample_rate, format='WAV')
            audio_bytes = wav_buffer.getvalue()

        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file_path = tmp_file.name

        # 调用语音识别模型（使用扩展参数）
        # 注意：实际实现中应使用您的模型生成方法
        # 调用模型生成
        res = asrmodel.generate(
            input=tmp_file_path,
            batch_size_s=batch_size_s,
            hotword=hotword
        )

        # 清理临时文件
        os.unlink(tmp_file_path)

        # 提取识别文本
        result_text = ""
        if isinstance(res, list) and len(res) > 0:
            result_text = res[0].get('text', '') if isinstance(res[0], dict) else str(res[0])

        # 根据请求的格式构建响应
        if response_format == "text":
            return result_text
        elif response_format == "json":
            return {"text": result_text}
        elif response_format == "verbose_json":
            return {
                "text": result_text,
                "language": language or "auto",
                "duration": len(audio_data) / sample_rate if 'audio_data' in locals() else 0,
                # 扩展信息
                "user": user,
                "hotword": hotword
            }
        else:
            # 简化处理其他格式
            return {"text": result_text}

    except Exception as e:
        # 清理临时文件（如果存在）
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        # OpenAI风格的错误响应
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": f"Audio processing error: {str(e)}",
                    "type": "server_error",
                    "code": 50001
                }
            }
        )


@router.get("/models", summary="ASR服务根路径")
async def root():
    return JSONResponse(content={
        "message": "语音识别API服务已启动",
        "endpoints": {
            "POST /": "语音识别接口"
        }
    })

@router.get("/health", summary="健康检查")
async def health_check():
    return {"status": "healthy", "model_loaded": model is not None}
